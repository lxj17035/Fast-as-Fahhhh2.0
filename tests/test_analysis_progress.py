from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from backend.analysis import AnalysisService
from tests.test_xinjie_integration import integrated, ready
from tests.test_drafting import valid_output


def test_running_analysis_visible_deduplicated_and_replaced(integrated):
    client, _, enquiry = integrated
    quote = ready(client, enquiry)
    app = client.app.state.quotation_app
    entered, release = Event(), Event()
    def extract(*args):
        entered.set()
        assert release.wait(10)
        return valid_output()
    app.drafts.extractor = Mock(extract=Mock(side_effect=extract))
    service = AnalysisService(app.drafts)
    with ThreadPoolExecutor() as pool:
        job = pool.submit(service.run,enquiry['id'])
        try:
            assert entered.wait(10)
            pending = service.latest(enquiry['id'])
            assert pending['status']=='running'
            duplicate=service.run(enquiry['id'])
            assert duplicate['id']==pending['id']
            assert app.drafts.extractor.extract.call_count==1
            assert app.quotations.get(quote['id'])==quote
        finally:
            release.set()
        finished=job.result(10)
    assert finished['id']==pending['id']
    assert service.latest(enquiry['id'])['status']=='completed'


def test_abandoned_analysis_can_be_retried_without_blocking_manual_save(integrated):
    client,_,enquiry=integrated
    q=ready(client,enquiry)
    app=client.app.state.quotation_app
    service=AnalysisService(app.drafts)
    app.drafts.extractor=Mock(extract=Mock(return_value=valid_output()))
    result=service.run(enquiry['id'])
    result.update(status='running',createdAt=(datetime.now(timezone.utc)-timedelta(minutes=4)).isoformat())
    with app.store.transaction():
        app.store.put('enquiry_analyses',result['id'],result)
    assert service.latest(enquiry['id'])['status']=='failed'
    saved=client.patch(f"/api/quotations/{q['id']}",json={'version':q['version'],'notes':'Manual review'}).json()
    assert saved['notes']=='Manual review'
    assert service.run(enquiry['id'])['status']=='completed'
