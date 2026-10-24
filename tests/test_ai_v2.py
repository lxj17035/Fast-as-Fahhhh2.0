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
    assert json.loads(captured[0]['messages'][1]['content'])['businessContext'] == context
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
