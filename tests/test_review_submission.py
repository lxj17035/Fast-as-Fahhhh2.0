import pytest
from tests.test_xinjie_integration import integrated, draft, ready
from backend.quotation_changes import QuotationChanges


def submit(client, q, role='sales', **extra):
    return client.post(f"/api/quotations/{q['id']}/submit-review", headers={'X-Demo-Actor': role},
                       json={'version': q['version'], 'sourceMessageIds': q['reviewedMessageIds'], **extra})


def test_submit_persists_exact_unpriced_version_without_preview(integrated):
    client, sender, enquiry = integrated
    q = draft(client, enquiry)
    path = f"/api/quotations/{q['id']}"
    q = client.patch(path, headers={'X-Demo-Actor':'sales'}, json={'version':q['version'],
        'client':{'name':'Fictional Client'}, 'items':[{'description':'Shirts','quantity':'20','unit':'pcs'}],
        'missingInformation':[]}).json()
    response = submit(client, q)
    assert response.status_code == 200, response.text
    saved = client.get(path).json()
    assert saved['reviewSubmission']['version'] == q['version']
    assert saved['reviewSubmission']['sourceMessageIds'] == q['reviewedMessageIds']
    assert saved['total'] is None
    assert sender.calls == [] and sender.text_calls == []
    assert any(a['action']=='quotation_submitted' for a in client.get(f"/api/enquiries/{enquiry['id']}").json()['activity'])
    q = client.patch(path, headers={'X-Demo-Actor':'sales'},json={'version':q['version'],'notes':'Updated'}).json()
    assert q['reviewSubmission']['version'] != q['version']
    assert q['reviewSubmission']['invalidatedBy'] == 'sales'
    assert submit(client,q).status_code == 200


def test_submit_rejects_incomplete_stale_and_unreviewed_sources(integrated, engine):
    client, _, enquiry = integrated
    q = draft(client,enquiry)
    assert submit(client,q).status_code == 422
    q = ready(client,enquiry)
    assert submit(client,q,version=q['version']-1).status_code == 409
    assert submit(client,q,sourceMessageIds=[]).status_code == 409
    assert submit(client,q,role='ai').status_code in (401,403)
    assert submit(client,q).status_code == 200
    from app.database import save_update
    save_update(engine, 99100, 99100, -1001234567890, 'Actually thirty shirts')
    assert submit(client,q).status_code == 409
    assert client.get(f"/api/quotations/{q['id']}/review",params={'version':q['version']},headers={'X-Demo-Actor':'pm'}).status_code == 409


@pytest.mark.parametrize('status',['sending','sent','send_uncertain'])
def test_submit_cannot_unlock_delivery(integrated,status):
    client,_,enquiry=integrated
    q=ready(client,enquiry)
    store=client.app.state.quotation_app.store
    with store.transaction():
        saved=store.get('quotations',q['id']); saved['status']=status; store.put('quotations',q['id'],saved)
    assert submit(client,q).status_code == 409


def test_ai_apply_invalidates_handoff_and_preserves_prices(integrated):
    client,_,enquiry=integrated
    q=ready(client,enquiry)
    assert submit(client,q).status_code == 200
    app=client.app.state.quotation_app
    changes=QuotationChanges(app.quotations)
    proposal=changes.suggest(q['id'],[{'type':'UPDATE_ITEM','index':0,'data':{'quantity':'30'}}])
    saved=changes.apply(q['id'],{'version':q['version'],'suggestion_set_id':proposal['id'],
                               'selected':[proposal['changes'][0]['id']]},'sales')
    assert saved['items'][0]['unitPrice']=='25.00'
    assert saved['reviewSubmission']['version'] != saved['version']
