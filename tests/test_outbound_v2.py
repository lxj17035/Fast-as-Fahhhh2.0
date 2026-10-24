"""A5 component-aware transport: real saved PDFs, mocked Telegram only."""
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import select, text

from app.database import send_attempts
from app.main import create_app
from app.telegram_client import DeliveryResult
from tests.test_xinjie_integration import integrated, ready, preview, deliver, RecordingTelegram
from tests.test_delivery_retry import retry, attempts
from tests.test_routing_v2 import receive


def test_pdf_and_summary_match_saved_review(integrated, engine, update):
    client, sender, enquiry = integrated
    quote = ready(client, enquiry)
    review = client.get(f"/api/quotations/{quote['id']}/review", params={'version': quote['version']},
                        headers={'X-Demo-Actor': 'pm'}).json()
    pdf = preview(client, quote).content
    assert deliver(client, quote).status_code == 200
    assert sender.calls == [(update['message']['chat']['id'], pdf)]
    assert sender.text_calls == [(update['message']['chat']['id'], review['telegram_summary'])]
    with engine.connect() as connection:
        row = connection.execute(select(send_attempts)).mappings().one()
    assert row['pdf_status'] == row['summary_status'] == row['status'] == 'sent'
    assert row['pdf_sha256'] == sha256(pdf).hexdigest()
    assert row['summary_text'] == review['telegram_summary']
    rendered = '\n'.join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    for value in [quote['total'], quote['issueDate'], quote['expiryDate']]:
        assert value in rendered and value in row['summary_text']
    history = client.get(f"/api/enquiries/{enquiry['id']}/conversation").json()['items']
    assert len([m for m in history if m.get('kind') == 'quotation_summary']) == 1
    assert len([m for m in history if m.get('kind') == 'quotation_pdf']) == 1


def test_confirmed_summary_failure_retries_only_unchanged_summary(integrated, engine):
    client, sender, enquiry = integrated
    quote = ready(client, enquiry)
    pdf = preview(client, quote).content
    sender.send_text = Mock(side_effect=[DeliveryResult('failed', error_code='telegram_403'),
                                         DeliveryResult('sent', message_id='9001')])
    first = deliver(client, quote)
    assert first.status_code == 502
    failed_id = first.json()['attempt_id']
    assert attempts(client, enquiry)[0]['pdf_status'] == 'sent'
    assert attempts(client, enquiry)[0]['summary_status'] == 'failed'
    assert client.get(f"/api/quotations/{quote['id']}").json()['status'] == 'send_failed'
    edited = client.patch(f"/api/quotations/{quote['id']}", json={'version': quote['version'], 'notes': 'Changed'})
    assert edited.status_code == 409
    assert deliver(client, quote).status_code == 409
    assert retry(client, quote, failed_id, actor='sales').status_code == 403
    assert retry(client, quote, failed_id).status_code == 200
    assert len(sender.calls) == 1
    assert sender.send_text.call_args_list[0] == sender.send_text.call_args_list[1]
    assert retry(client, quote, failed_id).status_code == 409
    with engine.connect() as connection:
        rows = connection.execute(select(send_attempts)).mappings().all()
    assert len(rows) == 2 and all(r['pdf_bytes'] == pdf and r['pdf_status'] == 'sent' for r in rows)
    assert len({r['summary_text'] for r in rows}) == 1
    history = client.get(f"/api/enquiries/{enquiry['id']}/conversation").json()['items']
    assert len([m for m in history if m.get('kind') == 'quotation_pdf']) == 1


@pytest.mark.parametrize('outcome', ['unknown', 'exception'])
def test_uncertain_summary_holds_without_reupload(integrated, outcome):
    client, sender, enquiry = integrated
    quote = ready(client, enquiry)
    preview(client, quote)
    sender.send_text = Mock(side_effect=TimeoutError('private') if outcome == 'exception' else None,
                            return_value=DeliveryResult('unknown', error_code='telegram_timeout'))
    response = deliver(client, quote)
    assert response.status_code == 202
    [attempt] = attempts(client, enquiry)
    assert attempt['pdf_status'] == 'sent' and attempt['summary_status'] == 'unknown'
    assert not attempt['can_retry'] and attempt['requires_verification']
    assert retry(client, quote, response.json()['attempt_id']).status_code == 409
    assert len(sender.calls) == sender.send_text.call_count == 1


def test_pdf_failure_does_not_send_summary(integrated):
    client, sender, enquiry = integrated
    quote = ready(client, enquiry)
    preview(client, quote)
    sender.result = DeliveryResult('failed', error_code='telegram_403')
    assert deliver(client, quote).status_code == 502
    assert sender.text_calls == []
    assert attempts(client, enquiry)[0]['summary_status'] == 'not_attempted'


def test_summary_retry_after_new_message_keeps_enquiry_for_review(integrated, headers, update):
    client, sender, enquiry = integrated
    quote = ready(client, enquiry)
    preview(client, quote)
    sender.send_text = Mock(side_effect=[DeliveryResult('failed', error_code='telegram_403'),
                                         DeliveryResult('sent', message_id='9001')])
    first = deliver(client, quote).json()['attempt_id']
    receive(client, headers, update, 1, 'Actually 30 shirts', reply=update['message']['message_id'])
    assert preview(client, quote).content == sender.calls[0][1]
    reviewed = client.get(f"/api/quotations/{quote['id']}/review", params={'version': quote['version']},
                          headers={'X-Demo-Actor': 'pm'})
    assert reviewed.status_code == 200
    assert reviewed.json()['delivery_mode'] == 'summary_only'
    assert reviewed.json()['source_message_ids'] == [str(update['update_id'])]
    assert retry(client, quote, first).status_code == 200
    assert len(sender.calls) == 1
    assert client.get(f"/api/enquiries/{enquiry['id']}").json()['status'] == 'needs_review'


def test_partial_delivery_survives_restart(integrated, engine, settings):
    client, sender, enquiry = integrated
    quote = ready(client, enquiry)
    preview(client, quote)
    sender.send_text = Mock(return_value=DeliveryResult('failed', error_code='telegram_403'))
    first = deliver(client, quote).json()['attempt_id']
    reopened_sender = RecordingTelegram()
    with TestClient(create_app(replace(settings, enable_demo_approval=True), engine,
                              telegram_sender=reopened_sender)) as reopened:
        assert retry(reopened, quote, first).status_code == 200
    assert reopened_sender.calls == [] and len(reopened_sender.text_calls) == 1


def test_component_schema_upgrade_preserves_legacy_history(integrated, engine, settings):
    if engine.dialect.name != 'postgresql':
        pytest.skip('Runtime migration is PostgreSQL only')
    client, sender, enquiry = integrated
    quote = ready(client, enquiry)
    pdf = preview(client, quote).content
    assert deliver(client, quote).status_code == 200
    with engine.begin() as connection:
        for column in ['pdf_status', 'summary_status', 'summary_provider_message_id']:
            connection.execute(text('ALTER TABLE send_attempts DROP COLUMN ' + column))
    for _ in range(2):
        with TestClient(create_app(replace(settings, enable_demo_approval=True), engine,
                                  telegram_sender=sender)) as reopened:
            assert deliver(reopened, quote).status_code == 409
    with engine.connect() as connection:
        row = connection.execute(select(send_attempts)).mappings().one()
    assert row['pdf_bytes'] == pdf and row['status'] == 'sent'
    assert row['pdf_status'] is None and row['summary_status'] is None


def test_replies_to_reused_pdf_and_summary_keep_one_enquiry(integrated, headers, update):
    client, sender, enquiry = integrated
    quote = ready(client, enquiry)
    preview(client, quote)
    sender.send_text = Mock(side_effect=[DeliveryResult('failed', error_code='telegram_403'),
                                         DeliveryResult('sent', message_id='9001')])
    first = deliver(client, quote).json()['attempt_id']
    assert retry(client, quote, first).status_code == 200
    receive(client, headers, update, 1, 'Is the PDF still valid?', reply=int(sender.result.message_id))
    receive(client, headers, update, 2, 'Thank you for the summary', reply=9001)
    assert len(client.get('/api/enquiries').json()['items']) == 1
    assert len(client.get(f"/api/enquiries/{enquiry['id']}").json()['messages']) == 3


def test_summary_acceptance_save_failure_retains_pending_hold(integrated, engine):
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError
    client, sender, enquiry = integrated
    quote = ready(client, enquiry)
    preview(client, quote)
    updates = []
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith('UPDATE SEND_ATTEMPTS'):
            updates.append(statement)
            if len(updates) == 2:
                raise OperationalError(statement, parameters, RuntimeError('synthetic failure'))
    event.listen(engine, 'before_cursor_execute', fail)
    try:
        response = deliver(client, quote)
    finally:
        event.remove(engine, 'before_cursor_execute', fail)
    assert response.status_code == 503
    [attempt] = attempts(client, enquiry)
    assert attempt['status'] == 'pending' and attempt['pdf_status'] == 'sent'
    assert not attempt['can_retry'] and attempt['requires_verification']
    assert retry(client, quote, response.json()['attempt_id']).status_code == 409
    assert len(sender.calls) == len(sender.text_calls) == 1
