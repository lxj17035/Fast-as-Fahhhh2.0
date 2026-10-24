"""Phase 4: complete HTTP journeys with real services/PDFs and mocked providers."""
from dataclasses import replace
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import select

from app.database import send_attempts
from app.main import create_app
from backend.drafting import DisabledExtractor
from backend.quotations import business_today, expiry_date
from tests.phase4_support import CASES, ScenarioTelegram, scenario_extractor
from tests.test_routing_v2 import receive


STAFF = {'X-Demo-Actor': 'sales'}
MANAGER = {'X-Demo-Actor': 'pm'}


@pytest.fixture
def journey(engine, settings):
    sender, contexts = ScenarioTelegram(), []
    application = create_app(replace(settings, enable_demo_approval=True), engine,
                             telegram_sender=sender, ai_extractor=DisabledExtractor())
    with TestClient(application) as client:
        service = application.state.quotation_app
        service.drafts.extractor = scenario_extractor(service.store, contexts)
        yield client, sender, contexts


def current_quote(client, enquiry_id):
    response = client.get(f'/api/enquiries/{enquiry_id}/quotation')
    assert response.status_code == 200, response.text
    return response.json()


def save(client, quote, fields, role=STAFF):
    response = client.patch(f"/api/quotations/{quote['id']}", headers=role,
                            json={'version': quote['version'], **fields})
    assert response.status_code == 200, response.text
    return response.json()


def final_send(client, quote):
    response = client.get(f"/api/quotations/{quote['id']}/review?version={quote['version']}", headers=MANAGER)
    assert response.status_code == 200, response.text
    review = response.json()
    response = client.get(review['pdf']['url'])
    assert response.status_code == 200, response.text
    pdf = response.content
    assert sha256(pdf).hexdigest() == review['pdf']['sha256']
    rendered = '\n'.join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    for value in (quote['number'], quote['total'], quote['issueDate'], quote['expiryDate']):
        assert value in rendered and value in review['telegram_summary']
    result = client.post(f"/api/quotations/{quote['id']}/send", headers=MANAGER,
                         json={'expected_version': quote['version'], 'approved': True})
    return result, review, pdf, rendered


def complete_journey(journey, headers, update, identity='printing'):
    client, sender, contexts = journey
    case = CASES[identity]
    assert client.patch('/api/business-profiles/active', json={'business_profile_id': identity}).status_code == 200
    receive(client, headers, update, 0, case['initial'])
    [enquiry] = client.get('/api/enquiries').json()['items']
    quote = current_quote(client, enquiry['id'])
    assert quote['draftMode'] == 'ai' and quote['items'][0]['unitPrice'] is None
    analysis = client.get(f"/api/enquiries/{enquiry['id']}/analysis").json()
    assert analysis['extraction']['clarificationSuggestions'] == [case['question']]
    assert sender.calls == []  # Extraction does not reply to customers.
    request = {'text': case['question'] + ' Thank you.', 'request_id': str(uuid4())}
    reply = client.post(f"/api/enquiries/{enquiry['id']}/messages", headers=STAFF, json=request)
    assert reply.status_code == 200, reply.text
    assert client.post(f"/api/enquiries/{enquiry['id']}/messages", headers=STAFF, json=request).json() == reply.json()
    assert len(sender.calls) == 1
    receive(client, headers, update, 1, case['answer'], reply=int(reply.json()['provider_message_id']))
    assert current_quote(client, enquiry['id']) == quote  # Customer answers never overwrite Staff work.
    analysis = client.get(f"/api/enquiries/{enquiry['id']}/analysis").json()
    assert not analysis['stale'] and analysis['extraction']['missingInformation'] == []
    assert [m['actor'] for m in contexts[-1]['conversation']['incoming']] == ['customer', 'customer']
    assert contexts[-1]['conversation']['outgoing'][0]['actor'] == 'sales'
    # Saving without acknowledging current messages cannot produce a final review.
    quote = save(client, quote, {'items': [dict(item_name=case['name'], quantity=case['quantity'],
                      unit=case['unit'], notes=case['notes'])], 'missingInformation': []})
    stale = client.get(f"/api/quotations/{quote['id']}/review?version={quote['version']}", headers=MANAGER)
    assert stale.status_code == 409
    ids = [m['update_id'] for m in client.get(f"/api/enquiries/{enquiry['id']}").json()['messages']]
    quote = save(client, quote, {'reviewedMessageIds': ids})
    assert quote['items'][0]['unitPrice'] is None
    # Manager owns price and reuses the existing calendar-month engine.
    issue = business_today().isoformat()
    quote = save(client, quote, {'issueDate': issue, 'validity': '1m', 'items': [dict(
        item_name=case['name'], quantity=case['quantity'], unit=case['unit'],
        notes=case['notes'], unit_price=case['price'])]}, MANAGER)
    assert quote['expiryDate'] == expiry_date(issue, '1m')
    result, review, pdf, rendered = final_send(client, quote)
    assert result.status_code == 200, result.text
    assert sender.calls == [('text', update['message']['chat']['id'], request['text']),
                            ('pdf', update['message']['chat']['id'], pdf),
                            ('text', update['message']['chat']['id'], review['telegram_summary'])]
    history = client.get(f"/api/enquiries/{enquiry['id']}/conversation").json()['items']
    assert [m['direction'] for m in history] == ['incoming', 'outgoing', 'incoming', 'outgoing', 'outgoing']
    assert [m['actor'] for m in history] == ['customer', 'sales', 'customer', 'pm', 'pm']
    assert [m.get('kind') for m in history[-2:]] == ['quotation_pdf', 'quotation_summary']
    times = [datetime.fromisoformat(m['created_at']) for m in history]
    assert times == sorted(times) and all(t.tzinfo for t in times)
    detail = client.get(f"/api/enquiries/{enquiry['id']}").json()
    assert detail['status'] == 'sent'
    assert len(detail['messages']) == 2 and len(detail['delivery_attempts']) == 1
    assert detail['messages'][0]['text'] == case['initial'] and detail['messages'][1]['text'] == case['answer']
    assert detail['delivery_attempts'][0]['pdf_status'] == detail['delivery_attempts'][0]['summary_status'] == 'sent'
    assert review['source_message_ids'] == quote['reviewedMessageIds'] == ids
    return enquiry, quote, review, pdf, rendered


def test_t1_printing_complete_journey(journey, engine, headers, update):
    client, _, _ = journey
    enquiry, quote, review, pdf, rendered = complete_journey(journey, headers, update)
    assert quote['total'] == '750.00' and CASES['printing']['notes'] in rendered
    with engine.connect() as connection:
        attempt = connection.execute(select(send_attempts)).mappings().one()
    assert attempt['version'] == quote['version'] and attempt['pdf_bytes'] == pdf
    assert attempt['summary_text'] == review['telegram_summary']
    assert client.get(f"/api/enquiries/{enquiry['id']}/quotation").json()['status'] == 'sent'


@pytest.mark.parametrize('identity,total', [('cleaning', '361.00'), ('repair', '95.75')])
def test_t2_services_complete_journey_and_pinned_scope(journey, headers, update, identity, total):
    client, _, contexts = journey
    company = 'Fictional ' + identity.title() + ' Acceptance Services'
    assert client.patch(f'/api/business-profiles/{identity}', json={'companyName': company}).status_code == 200
    enquiry, quote, review, pdf, rendered = complete_journey(journey, headers, update, identity)
    assert quote['total'] == total and quote['business_profile_id'] == identity
    assert quote['items'][0]['unit'] == CASES[identity]['unit']
    assert CASES[identity]['notes'] in rendered and company in rendered
    assert review['business_profile']['companyName'] == company
    assert all(c['businessProfile']['id'] == identity and c['company']['companyName'] == company for c in contexts)
    assert all('T-shirt' not in str(c) and 'Print Studio' not in str(c) for c in contexts)
    assert 'T-shirt' not in rendered and 'Print Studio' not in rendered
    assert client.patch('/api/business-profiles/active', json={'business_profile_id': 'printing'}).status_code == 200
    assert client.get('/api/enquiries').json()['items'] == []
    for path in (f"/api/enquiries/{enquiry['id']}", f"/api/enquiries/{enquiry['id']}/conversation",
                 f"/api/quotations/{quote['id']}", review['pdf']['url']):
        assert client.get(path).status_code == 404
    client.patch('/api/business-profiles/active', json={'business_profile_id': identity})
    assert client.get(review['pdf']['url']).content == pdf
    assert current_quote(client, enquiry['id'])['business_profile_id'] == identity


def fork(client, original, relationship='revision', target=None):
    response = client.post(f"/api/quotations/{original['id']}/fork", headers=STAFF,
        json={'version': original['version'], 'relationship': relationship,
              **({'enquiry_id': target} if target else {})})
    assert response.status_code == 200, response.text
    return response.json()


def prepare_fork(client, quote):
    ids = [m['update_id'] for m in client.get(f"/api/enquiries/{quote['enquiryId']}").json()['messages']]
    quote = save(client, quote, {'reviewedMessageIds': ids, 'missingInformation': [],
        'client': {'name': 'Fictional Customer'}, 'items': [dict(item_name='Revised event shirts',
        quantity=40, unit='pcs', notes='Confirmed amendment; blue cotton')]})
    assert quote['total'] is None
    return save(client, quote, {'items': [dict(item_name='Revised event shirts', quantity=40,
        unit='pcs', notes='Confirmed amendment; blue cotton', unit_price='25.00')]}, MANAGER)


@pytest.mark.parametrize('intent', ['revision', 'additional', 'unclear'])
def test_t3_post_send_relationships_keep_original_history(journey, headers, update, intent):
    client, sender, _ = journey
    enquiry, original, review, pdf, _ = complete_journey(journey, headers, update)
    saved_original = client.get(f"/api/quotations/{original['id']}").json()
    original_calls = list(sender.calls)
    if intent == 'additional':
        receive(client, headers, update, 2, 'New quotation for a separate independent order of 40 shirts')
        target = next(e['id'] for e in client.get('/api/enquiries').json()['items'] if e['id'] != enquiry['id'])
        wrong = client.post(f"/api/quotations/{original['id']}/fork", headers=STAFF,
            json={'version': original['version'], 'relationship': intent, 'enquiry_id': enquiry['id']})
        assert wrong.status_code == 422
        child = fork(client, original, intent, target)
        assert child['enquiryId'] == target
    else:
        receive(client, headers, update, 2, 'Amend the original to 40 shirts' if intent == 'revision'
                else 'I need 40 shirts; not sure how to group this', reply=700003)
        analysis = client.get(f"/api/enquiries/{enquiry['id']}/analysis").json()
        assert analysis['relationshipIntent'] == intent and analysis['suggestionSetId'] is None
        assert client.get(f"/api/quotations/{original['id']}").json() == saved_original
        if intent == 'unclear':
            assert analysis['changeWarnings'] and analysis['extraction']['clarificationSuggestions']
            assert len(client.get(f"/api/enquiries/{enquiry['id']}/quotations").json()['items']) == 1
            assert sender.calls == original_calls  # Advisory AI does not send or fork.
            question = analysis['extraction']['clarificationSuggestions'][0]
            result = client.post(f"/api/enquiries/{enquiry['id']}/messages", headers=STAFF,
                json={'text': question, 'request_id': str(uuid4())})
            assert result.status_code == 200
            receive(client, headers, update, 3, 'Amend the original quotation to 40 shirts',
                    reply=int(result.json()['provider_message_id']))
            assert client.get(f"/api/enquiries/{enquiry['id']}/analysis").json()['relationshipIntent'] == 'revision'
        child = fork(client, original)
        assert child['enquiryId'] == enquiry['id']
    assert child['id'] != original['id'] and child['parentQuotationId'] == original['id']
    assert child['relationship'] == ('revision' if intent == 'unclear' else intent)
    assert child['total'] is None and all(i['unitPrice'] is None for i in child['items'])
    child = prepare_fork(client, child)
    result, child_review, child_pdf, _ = final_send(client, child)
    assert result.status_code == 200, result.text
    assert child['total'] == '1000.00' and child_pdf != pdf
    assert child_review['source_message_ids'] == child['reviewedMessageIds']
    assert client.get(review['pdf']['url']).content == pdf
    assert client.get(f"/api/quotations/{original['id']}").json() == saved_original
    # Original and child delivery histories retain their own immutable snapshots.
    history = client.get(f"/api/enquiries/{enquiry['id']}/conversation").json()['items']
    original_summary = [m for m in history if m.get('kind') == 'quotation_summary'
                        and m.get('quotation_id', '').replace('-', '') == original['id']]
    assert len(original_summary) == 1 and original_summary[0]['text'] == review['telegram_summary']


def test_t3_authority_scope_stale_duplicates_and_unknown_hold(journey, headers, update):
    client, sender, _ = journey
    enquiry, original, review, pdf, _ = complete_journey(journey, headers, update)
    receive(client, headers, update, 2, 'Amend the original to 40 shirts', reply=700003)
    child = prepare_fork(client, fork(client, original))
    path = f"/api/quotations/{child['id']}"
    approval = {'expected_version': child['version'], 'approved': True}
    before = len(sender.calls)
    for actor, status in [('sales', 403), ('ai', 401)]:
        role = {'X-Demo-Actor': actor}
        assert client.post(path + '/send', headers=role, json=approval).status_code == status
        assert client.patch(path, headers=role, json={'version': child['version'], 'items': [
            dict(item_name='Forbidden price', quantity=1, unit_price=1)]}).status_code == status
    assert client.post(path + '/send', headers=MANAGER, json={**approval, 'chat_id': -999}).status_code == 422
    assert client.post(f"/api/quotations/{original['id']}/send", headers=MANAGER,
        json={'expected_version': original['version'], 'approved': True}).status_code == 409
    assert len(sender.calls) == before
    assert client.get(path + f"/review?version={child['version']}", headers=MANAGER).status_code == 200
    stale_version = child['version']
    child = save(client, child, {'notes': 'Manager reviewed amendment'}, MANAGER)
    assert client.post(path + '/send', headers=MANAGER, json=approval).status_code == 409
    assert client.get(path + f'/pdf?version={stale_version}').status_code == 409
    assert client.get(path + f"/review?version={child['version']}", headers=MANAGER).status_code == 200
    client.patch('/api/business-profiles/active', json={'business_profile_id': 'repair'})
    assert client.get(path + f"/review?version={child['version']}", headers=MANAGER).status_code == 404
    assert client.patch(path, headers=MANAGER, json={'version': child['version'], 'notes': 'Wrong profile'}).status_code == 404
    assert client.post(path + '/send', headers=MANAGER, json={**approval, 'expected_version': child['version']}).status_code == 404
    assert client.post(f"/api/enquiries/{enquiry['id']}/messages", headers=STAFF,
        json={'text': 'Wrong scope', 'request_id': str(uuid4())}).status_code == 404
    client.patch('/api/business-profiles/active', json={'business_profile_id': 'printing'})
    assert current_quote(client, enquiry['id']) == child  # Wrong-scope reservation rolls back.
    assert len(sender.calls) == before
    sender.outcome = 'unknown'
    result, _, _, _ = final_send(client, child)
    assert result.status_code == 202
    assert len(sender.calls) == before + 1 and sender.calls[-1][0] == 'pdf'
    attempt_id = result.json()['attempt_id']
    for extra in ({}, {'retry_of_attempt_id': attempt_id}):
        response = client.post(path + '/send', headers=MANAGER,
            json={'expected_version': child['version'], 'approved': True, **extra})
        assert response.status_code == 409
    detail = client.get(f"/api/enquiries/{enquiry['id']}").json()
    attempt = next(a for a in detail['delivery_attempts'] if a['attempt_id'] == attempt_id)
    assert attempt['requires_verification'] and not attempt['can_retry']
    assert detail['status'] != 'sent' and current_quote(client, enquiry['id'])['status'] == 'send_uncertain'
    assert client.get(review['pdf']['url']).content == pdf and len(sender.calls) == before + 1
