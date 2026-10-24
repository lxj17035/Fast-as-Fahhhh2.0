import { analysisCurrent } from './model.js';
export function availableChanges(s) {
  return s.suggestions.filter(set => !set.applied && set.changes.length && set.baseVersion === s.quote?.version &&
    JSON.stringify(set.conversationMessageIds) === JSON.stringify(s.detail.messages.map(m => m.update_id)));
}
export function analysisAction(s) {
  if (!s.quote || s.busy || s.analysis?.status === 'running' || analysisCurrent(s.analysis,s.quote,s.detail,s.conversation,s.assignments)) return null;
  return s.analysis?.status === 'failed' ? 'Retry analysis' : 'Analyze messages';
}
