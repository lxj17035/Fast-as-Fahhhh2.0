"""Validate/consolidate AI changes into the existing human-applied mechanism."""
import json

from backend.errors import AppError, object_fields
from backend.quotation_changes import QuotationChanges, validate_change


def validate_proposals(changes):
    if not isinstance(changes, list) or len(changes) > 100:
        raise AppError('Invalid proposed changes')
    result = []
    for raw in changes:
        object_fields(raw, {'type', 'index', 'field', 'value', 'data'})
        # Strict model schemas include irrelevant keys as null.
        change = {k: v for k, v in raw.items() if v is not None}
        allowed = {'ADD_ITEM': {'type', 'data'}, 'UPDATE_ITEM': {'type', 'index', 'data'},
                   'UPDATE_FIELD': {'type', 'field', 'value'}}.get(change.get('type'), set())
        object_fields(change, allowed)
        if isinstance(change.get('data'), dict):
            change['data'] = {k: v for k, v in change['data'].items() if v is not None or k == 'quantity'}
        result.append(validate_change(change))
    return result


def store_proposals(quotations, quote, extracted, source_ids):
    changes = validate_proposals(extracted.get('proposedChanges', []))
    intent = extracted.get('relationshipIntent', 'none')
    result = {'suggestionSetId': None, 'changeWarnings': [], 'relationshipIntent': intent}
    if intent == 'unclear':
        result['changeWarnings'].append('Ask the customer whether to revise or request an additional quotation')
    if quote['status'] not in {'draft', 'send_failed'}:
        if changes:
            result['changeWarnings'].append('Sent quotation is immutable; Staff must explicitly create a revision or additional quotation')
        return result
    # Provider output is checked against the exact saved version, inside analysis transaction.
    consolidated = []
    seen, updated = set(), set()
    names = {i['item_name'].strip().casefold() for i in quote['items']}
    for change in changes:
        key = json.dumps(change, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        if change['type'] == 'ADD_ITEM':
            name = change['data'].get('item_name', change['data'].get('description', '')).strip().casefold()
            if not name or name in names:
                result['changeWarnings'].append('Review an existing or unnamed item instead of adding a duplicate')
                continue
            names.add(name)
        elif change['type'] == 'UPDATE_ITEM':
            index = change['index']
            if index >= len(quote['items']):
                raise AppError('Suggested item index is unavailable')
            if index in updated:
                result['changeWarnings'].append('Conflicting updates to one item require fresh Staff clarification')
                # Do not pick one conflicting correction without review.
                consolidated = [c for c in consolidated if not (c['type'] == 'UPDATE_ITEM' and c['index'] == index)]
                continue
            updated.add(index)
        consolidated.append(change)
    if consolidated:
        proposal = QuotationChanges(quotations).suggest(quote['id'], consolidated, source_ids)
        result['suggestionSetId'] = proposal['id']
    return result
