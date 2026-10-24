"""Read-only AI analysis snapshots; no customer send or quotation mutation."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.database import message_links, telegram_updates, outgoing_messages
from backend.drafting import business_context, ProviderError
from backend.errors import AppError
from backend.settings import require_profile


def evidence(store, enquiry):
    """Read pinned scope directly; do not substitute the current active profile."""
    with store.reading() as connection:
        rows = connection.execute(select(telegram_updates, message_links).join(
            message_links, message_links.c.update_id == telegram_updates.c.update_id
        ).where(message_links.c.business_profile_id == enquiry['business_profile_id'],
                telegram_updates.c.chat_id == int(enquiry['chatId']),
                (message_links.c.enquiry_id == enquiry['id']) | (message_links.c.status == 'needs_assignment'))
            .order_by(telegram_updates.c.received_at, telegram_updates.c.update_id)).mappings().all() if enquiry.get('providerUpdateId') else []
        outgoing = connection.execute(select(outgoing_messages).where(
            outgoing_messages.c.enquiry_id == enquiry['id'], outgoing_messages.c.status == 'sent')
            .order_by(outgoing_messages.c.created_at, outgoing_messages.c.id)).mappings().all()
    messages = [{'update_id': str(r['update_id']), 'message_id': str(r['message_id']),
                 'actor': 'customer', 'text': r['original_text'], 'assignment': r['status'],
                 'created_at': r['received_at'].isoformat(),
                 'reply_to_message_id': next((h['reply_to_message_id'] for h in r['history']
                                             if 'reply_to_message_id' in h), None)} for r in rows]
    return {'incoming': messages, 'outgoing': [{'actor': r['actor'], 'text': r['text'],
            'provider_message_id': r['provider_message_id'], 'created_at': r['created_at'].isoformat()} for r in outgoing]}


class AnalysisService:
    def __init__(self, drafts):
        self.drafts = drafts
        self.store, self.settings, self.quotations = drafts.store, drafts.settings, drafts.quotations

    def record_initial(self, enquiry, conversation, quote, extracted, failure):
        signature = {'sourceMessageIds': enquiry.get('messageUpdateIds', []),
                     'unassignedMessageIds': enquiry.get('unassignedMessageIds', []),
                     'conversation': conversation, 'baseVersion': quote['version'],
                     'quotationId': quote['id'], 'businessContext': business_context(self.settings, enquiry)}
        current = self.store.get('enquiries', enquiry['id'])
        result = {'id': uuid4().hex, 'enquiryId': enquiry['id'],
                  'business_profile_id': enquiry['business_profile_id'], 'signature': signature,
                  'status': ('manual' if quote['draftMode'] == 'manual' else 'failed' if failure else 'completed'), 'error': failure,
                  'extraction': extracted, 'resolvedAssignments': [],
                  'stale': evidence(self.store, current) != conversation,
                  'createdAt': datetime.now(timezone.utc).isoformat()}
        self.store.put('enquiry_analyses', result['id'], result)
        return result

    def latest(self, enquiry_id):
        enquiry = require_profile(self.store.get('enquiries', enquiry_id), self.settings.active_profile_id())
        rows = [a for a in self.store.list('enquiry_analyses') if a['enquiryId'] == enquiry['id']]
        return rows[-1] if rows else None

    def run(self, enquiry_id):
        with self.store.transaction():
            enquiry = self.store.get('enquiries', enquiry_id)
            quotes = [q for q in self.store.list('quotations') if q['enquiryId'] == enquiry_id]
            quote = quotes[-1] if quotes else None
            conversation = evidence(self.store, enquiry)
            context = {**business_context(self.settings, enquiry), 'enquiryId': enquiry_id,
                       'conversation': conversation, 'savedQuotation': quote}
            signature = {'sourceMessageIds': enquiry.get('messageUpdateIds', []),
                         'unassignedMessageIds': enquiry.get('unassignedMessageIds', []),
                         'conversation': conversation, 'baseVersion': quote['version'] if quote else None,
                         'quotationId': quote['id'] if quote else None, 'businessContext': business_context(self.settings, enquiry)}
            for row in reversed(self.store.list('enquiry_analyses')):
                if row['enquiryId'] == enquiry_id and row['signature'] == signature and row['status'] == 'completed' and not row.get('stale'):
                    return row
        try:
            extracted = self.drafts.extractor.extract(enquiry['text'], context)
            failure = None
        except ProviderError as error:
            extracted, failure = None, str(error)
        result = {'id': uuid4().hex, 'enquiryId': enquiry_id, 'business_profile_id': enquiry['business_profile_id'],
                  'signature': signature, 'status': 'failed' if failure else 'completed',
                  'error': failure, 'extraction': extracted,
                  'createdAt': datetime.now(timezone.utc).isoformat()}
        with self.store.transaction():
            current = self.store.get('enquiries', enquiry_id)
            current_quotes = [q for q in self.store.list('quotations') if q['enquiryId'] == enquiry_id]
            current_quote = current_quotes[-1] if current_quotes else None
            result['stale'] = (current.get('messageUpdateIds', []) != signature['sourceMessageIds'] or
                               evidence(self.store, current) != conversation or
                               (current_quote['id'], current_quote['version']) !=
                               (quote['id'], quote['version'])) if quote and current_quote else bool(quote or current_quote)
            # Assignment is optional and independently checked against stored receipts.
            result['resolvedAssignments'] = []
            if extracted and not result['stale']:
                from app.routing import resolve_ai_assignment
                for proposed in extracted.get('assignmentSuggestions', []):
                    try:
                        resolved = resolve_ai_assignment(self.store, enquiry_id, proposed)
                        result['resolvedAssignments'].append(resolved)
                    except AppError:
                        pass  # Unproven association remains for Staff.
                if result['resolvedAssignments']:
                    result['stale'] = True
            self.store.put('enquiry_analyses', result['id'], result)
        return result
