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
