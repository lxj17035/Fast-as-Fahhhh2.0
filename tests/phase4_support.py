"""Synthetic scenarios shared by API acceptance tests and the local browser fixture.

Runpod's HTTP transport and Telegram alone are replaced. No .env is loaded.
"""
import json
from copy import deepcopy

import httpx

from app.telegram_client import DeliveryResult
from backend.runpod import RunpodExtractor


CASES = {
    'printing': dict(name='Event T-shirts', unit='pcs', quantity=30, price='25.00',
                     notes='Cotton; blue front print', question='Please confirm print colour and quantity.',
                     initial='Fictional Events needs 20 cotton T-shirts with front print; please quote.',
                     answer='Actually 30 cotton T-shirts, blue front print, please revise the quantity.'),
}


class ScenarioTelegram:
    def __init__(self):
        self.calls = []
        self.outcome = 'sent'

    def _record(self, kind, chat_id, content):
        self.calls.append((kind, chat_id, content))
        return DeliveryResult(self.outcome, message_id=str(700000 + len(self.calls))
                              if self.outcome == 'sent' else None,
                              error_code='telegram_timeout' if self.outcome == 'unknown' else None)

    def send_text(self, chat_id, content):
        return self._record('text', chat_id, content)

    def send_pdf(self, chat_id, pdf):
        return self._record('pdf', chat_id, pdf)


def scenario_extractor(store, captured):
    def respond(request):
        payload = json.loads(request.content)
        context = json.loads(payload['messages'][1]['content'])['businessContext']
        captured.append(deepcopy(context))
        case = CASES[context['businessProfile']['id']]
        incoming = context['conversation']['incoming']
        answered = len(incoming) > 1
        intent = 'none'
        last = incoming[-1]['text'].lower()
        if (context.get('savedQuotation') or {}).get('status') == 'sent':
            intent = 'additional' if 'independent' in last else 'revision' if 'amend' in last else 'unclear'
        value = dict(summary='Synthetic service enquiry', clientName='Fictional Customer',
                     clientAddress=None, items=[dict(description=case['name'],
                     quantity=case['quantity'] if answered else None, unit=case['unit'],
                     notes=case['notes'] if answered else '')],
                     missingInformation=[] if answered else [case['question']],
                     clarificationSuggestions=(['Should this amend the original or be an independent quotation?']
                         if intent == 'unclear' else [] if answered else [case['question']]),
                     assignmentSuggestions=[], relationshipIntent=intent,
                     proposedChanges=[dict(type='UPDATE_ITEM', index=0, data=dict(
                         quantity=case['quantity'], notes=case['notes']))] if answered else [])
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop',
            'message': {'role': 'assistant', 'content': json.dumps(value)}}]})
    return RunpodExtractor('synthetic-not-a-key', store=store, values={},
                           transport=httpx.MockTransport(respond))
