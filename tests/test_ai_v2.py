import json
from unittest.mock import Mock

import httpx
import pytest

from backend.drafting import DraftService, OpenAIExtractor, business_context, INSTRUCTIONS
from backend.runpod import RunpodExtractor
from backend.settings import SettingsService
from backend.quotations import QuotationService
from backend.store import Store
from tests.test_drafting import response, valid_output
from tests.test_runpod import completion


@pytest.mark.parametrize('identity', ['printing', 'cleaning', 'repair'])
def test_pinned_profile_reaches_both_adapters(engine, identity):
    store = Store(engine=engine)
    settings = SettingsService(store)
    with store.transaction():
        store.put('enquiries', 'context-test', {'id': 'context-test', 'text': 'Fictional request',
                  'business_profile_id': identity, 'clientId': settings.demo_client_id(identity), 'source': 'demo'})
    settings.select_profile({'business_profile_id': 'repair' if identity != 'repair' else 'printing'})
    enquiry = store.get('enquiries', 'context-test')
    context = business_context(settings, enquiry)
    assert context['businessProfile'] == {'id': identity, 'industry': identity.title()}
    captured = []
    extractor = RunpodExtractor('synthetic', store=store, values={}, transport=httpx.MockTransport(
        lambda request: (captured.append(json.loads(request.content)) or httpx.Response(200, json=completion()))))
    DraftService(store, settings, QuotationService(store, settings), extractor).create('context-test')
    assert all(json.loads(captured[0]['messages'][1]['content'])['businessContext'][key] == value for key, value in context.items())
    transport = Mock(return_value=response())
    OpenAIExtractor('synthetic', 'test', transport).extract('Fictional', context)
    assert json.loads(transport.call_args.args[0]['input'])['businessContext'] == context
    assert 'Printing Shop' not in INSTRUCTIONS
    assert 'cannot set or' in INSTRUCTIONS


@pytest.mark.parametrize('field', ['business_profile_id', 'recipient', 'approved', 'price'])
def test_ai_cannot_return_authority_fields(field):
    value = valid_output()
    value[field] = 'untrusted'
    from backend.drafting import ProviderError
    with pytest.raises(ProviderError):
        OpenAIExtractor('synthetic', 'test', Mock(return_value=response(value))).extract('Fictional', {})


@pytest.mark.parametrize('identity,name,unit,notes', [
    ('printing', 'Flyers', 'pcs', 'A5, full colour'),
    ('cleaning', 'Office cleaning', 'visit', '120 square metres, windows excluded'),
    ('repair', 'Laptop repair', 'job', 'Fictional device X; replace stated keyboard')])
def test_generic_requirements_and_sufficiency(engine, identity, name, unit, notes):
    from backend.drafting import validate_extraction
    from backend.errors import AppError
    store = Store(engine=engine)
    settings = SettingsService(store)
    settings.select_profile({'business_profile_id': identity})
    value = valid_output()
    value['items'] = [{'description': name, 'quantity': 2, 'unit': unit, 'notes': notes}]
    extracted = validate_extraction(value)
    assert extracted['missingInformation'] == []
    quotes = QuotationService(store, settings)
    quote = quotes.create('synthetic', settings.demo_client_id(identity), extracted=extracted)
    assert quote['items'][0]['notes'] == notes and quote['items'][0]['unit'] == unit
    assert quote['total'] is None
    value['items'][0].update(quantity=None, unit=None)
    value['missingInformation'] = ['Confirm ambiguous service specification']
    incomplete = validate_extraction(value)
    assert incomplete['items'][0]['quantity'] is None
    assert len(incomplete['missingInformation']) == 3
    other = quotes.create('incomplete', settings.demo_client_id(identity), extracted=incomplete)
    with pytest.raises(AppError):
        quotes.validate_for_send(other['id'], 1, 'pm')


def test_no_items_cannot_be_declared_sufficient():
    from backend.drafting import validate_extraction
    value = valid_output()
    value['items'] = []
    assert validate_extraction(value)['missingInformation']


def test_followup_analysis_keeps_staff_edits_and_caches(engine, settings, headers, update):
    from dataclasses import replace
    from fastapi.testclient import TestClient
    from app.main import create_app
    from tests.test_routing_v2 import receive
    from backend.analysis import AnalysisService
    with TestClient(create_app(replace(settings, enable_demo_approval=True), engine)) as client:
        app = client.app.state.quotation_app
        transport = Mock(return_value=response())
        app.drafts.extractor = OpenAIExtractor('synthetic', 'test', transport)
        receive(client, headers, update, 0, 'Please quote 1000 flyers')
        enquiry = app.store.list('enquiries')[0]
        quote = app.store.list('quotations')[0]
        app.quotations.update(quote['id'], {'version': 1, 'notes': 'Staff edited'})
        value = valid_output()
        value['items'] = [{'description': 'Flyers', 'quantity': 1500, 'unit': 'pcs', 'notes': ''}]
        value['clarificationSuggestions'] = ['Could you confirm the paper size?']
        transport.return_value = response(value)
        receive(client, headers, update, 1, 'Actually 1500 flyers')
        analysis = AnalysisService(app.drafts).latest(enquiry['id'])
        assert analysis['extraction']['items'][0]['quantity'] == '1500'
        assert analysis['extraction']['clarificationSuggestions'] == value['clarificationSuggestions']
        assert app.quotations.get(quote['id'])['notes'] == 'Staff edited'
        assert app.quotations.get(quote['id'])['version'] == 2
        assert len(analysis['signature']['conversation']['incoming']) == 2
        assert not analysis['stale']
        assert client.get(f"/api/enquiries/{enquiry['id']}/analysis").json()['id'] == analysis['id']
        assert AnalysisService(app.drafts).run(enquiry['id'])['id'] == analysis['id']
        assert transport.call_count == 2
        assert client.post(f"/api/enquiries/{enquiry['id']}/analysis").status_code == 403
        assert app.store.list('enquiry_analyses')[0]['extraction']['items'][0]['unitPrice'] is None


def test_assignment_requires_customer_reference_to_exact_unresolved_message(client, engine, headers, update):
    from app.routing import assign_message, resolve_ai_assignment
    from app.xinjie_store import Store as IntegratedStore
    from backend.errors import AppError
    from tests.test_routing_v2 import receive
    receive(client, headers, update, 0, 'Please quote 1000 flyers')
    enquiry = client.app.state.quotation_app.store.list('enquiries')[0]
    ambiguous = receive(client, headers, update, 1, 'Maybe 1500?')
    confirmation = receive(client, headers, update, 2, 'This message is for ' + enquiry['id'],
                           reply=ambiguous['message']['message_id'])
    store = IntegratedStore(engine)
    proposal = {'update_id': str(ambiguous['update_id']), 'confirmation_update_id': str(confirmation['update_id'])}
    with pytest.raises(AppError):
        resolve_ai_assignment(store, enquiry['id'], proposal)
    assign_message(store, confirmation['update_id'], {'action': 'assign', 'enquiry_id': enquiry['id']}, 'sales')
    with pytest.raises(AppError):
        resolve_ai_assignment(store, enquiry['id'], {**proposal, 'confirmation_update_id': str(update['update_id'])})
    result = resolve_ai_assignment(store, enquiry['id'], proposal)
    assert result['assigned_by'] == 'ai'
    assert result['history'][-1]['confirmation_update_id'] == str(confirmation['update_id'])
    with pytest.raises(AppError):
        resolve_ai_assignment(store, enquiry['id'], proposal)


def test_analysis_race_marks_snapshot_stale_and_never_acknowledges_new_message(engine):
    from backend.analysis import AnalysisService
    from app.database import save_update
    store = Store(engine=engine)
    settings = SettingsService(store)
    save_update(engine, 1, 1, -123, 'Please quote 1000 flyers')
    enquiry = store.list('enquiries')[0]
    drafts = DraftService(store, settings, QuotationService(store, settings))
    quote = drafts.create(enquiry['id'], manual=True)
    def extract(message, context):
        save_update(engine, 2, 2, -123, 'Actually 1500 flyers')
        return valid_output()
    drafts.extractor = Mock(extract=extract)
    result = AnalysisService(drafts).run(enquiry['id'])
    assert result['stale']
    assert result['signature']['sourceMessageIds'] == ['1']
    assert drafts.quotations.get(quote['id'])['reviewedMessageIds'] == ['1']
