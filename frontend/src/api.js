export class ApiError extends Error {
  constructor(message, status = 0, fields = {}, data = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.fields = fields;
    this.data = data;
  }
}

export function errorDetails(data) {
  const detail = data?.detail ?? data;
  if (typeof detail === 'string') return { message: detail, fields: {} };
  if (Array.isArray(detail)) {
    return {
      message: 'Please check the highlighted request values.',
      fields: Object.fromEntries(detail.map(item => [(item.loc || []).slice(1).join('.'), item.msg || 'Invalid value'])),
    };
  }
  return { message: detail?.message || data?.error || 'The request could not be completed.', fields: detail?.fields || data?.fields || {} };
}

export class Api {
  constructor(base, fetcher = globalThis.fetch.bind(globalThis)) {
    this.base = base.replace(/\/$/, '');
    this.fetcher = fetcher;
  }

  async request(path, { method = 'GET', body, role, pdf = false, delivery = false, messageDelivery = false, nullable = false } = {}) {
    const headers = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (role) headers['X-Demo-Actor'] = role;
    let response;
    try {
      response = await this.fetcher(this.base + path, {
        method, headers, cache: 'no-store',
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
        signal: AbortSignal.timeout((delivery || messageDelivery) ? 120_000 : 90_000),
      });
    } catch {
      throw new ApiError((delivery || messageDelivery)
        ? 'Delivery could not be confirmed. Check the original Telegram chat and refresh the delivery history. Do not send again.'
      : 'Cannot reach the API. Check the server connection and try again.');
    }
    if (pdf && response.ok) {
      const blob = await response.blob();
      const version = Number(response.headers.get('X-Quotation-Version'));
      if (!blob.type.includes('application/pdf') || !Number.isInteger(version) || version < 1) {
        throw new ApiError('The API did not return a versioned PDF.', 502);
      }
      return { blob, version };
    }
    let data;
    try { data = await response.json(); }
    catch { throw new ApiError('The API returned an unreadable response. Refresh before continuing.', response.status); }
    if (nullable && data === null && response.ok) return null;
    if (!data || typeof data !== 'object' || Array.isArray(data)) {
      throw new ApiError('The API returned an invalid response. Refresh before continuing.', response.status);
    }
    if (messageDelivery && data.status && ['sent', 'failed', 'unknown', 'pending'].includes(data.status) && data.id) return data;
    if (messageDelivery && response.ok) throw new ApiError('Message delivery is unconfirmed. Refresh history before sending anything else.', response.status);
    // An explicit rejection is an HTTP 502 but still a persisted delivery outcome.
    if (delivery && data.attempt_id && ['sent', 'failed', 'unknown'].includes(data.status)) return data;
    if (delivery && response.ok) {
      throw new ApiError('Delivery could not be confirmed. Check the original chat and refresh delivery history. Do not send again.', response.status);
    }
    if (!response.ok) {
      const { message, fields } = errorDetails(data);
      throw new ApiError(message, response.status, fields, data);
    }
    return data;
  }

  health() { return this.request('/api/health'); }
  enquiries(offset = 0, limit = 25) { return this.request(`/api/enquiries?limit=${limit}&offset=${offset}`); }
  enquiry(id) { return this.request(`/api/enquiries/${encodeURIComponent(id)}`); }
  quotation(id) { return this.request(`/api/enquiries/${encodeURIComponent(id)}/quotation`); }
  draft(id, manual) { return this.request(`/api/enquiries/${encodeURIComponent(id)}/draft`, { method: 'POST', body: { manual } }); }
  saveQuote(id, body, role) { return this.request(`/api/quotations/${encodeURIComponent(id)}`, { method: 'PATCH', body, role }); }
  pdf(id, version) { return this.request(`/api/quotations/${encodeURIComponent(id)}/pdf?version=${version}`, { pdf: true }); }
  send(id, version, retryId) {
    const body = { expected_version: version, approved: true };
    if (retryId) body.retry_of_attempt_id = retryId;
    return this.request(`/api/quotations/${encodeURIComponent(id)}/send`, { method: 'POST', body, role: 'pm', delivery: true });
  }
  suggestions(id) { return this.request(`/api/quotations/${encodeURIComponent(id)}/suggestions`); }
  applyChanges(id, body, role) { return this.request(`/api/quotations/${encodeURIComponent(id)}/apply-changes`, { method: 'POST', body, role }); }
  fork(id, body, role) { return this.request(`/api/quotations/${encodeURIComponent(id)}/fork`, { method: 'POST', body, role }); }
  conversation(id) { return this.request(`/api/enquiries/${encodeURIComponent(id)}/conversation`); }
  analysis(id, role) { return this.request(`/api/enquiries/${encodeURIComponent(id)}/analysis`, role ? { method: 'POST', body: {}, role, nullable: true } : { nullable: true }); }
  message(id, body, role) { return this.request(`/api/enquiries/${encodeURIComponent(id)}/messages`, { method: 'POST', body, role, messageDelivery: true }); }
  assignments() { return this.request('/api/assignments'); }
  assign(id, body, role) { return this.request(`/api/assignments/${encodeURIComponent(id)}`, { method: 'POST', body, role }); }
  settings() { return this.request('/api/settings'); }
  profiles() { return this.request('/api/business-profiles'); }
  selectProfile(id) { return this.request('/api/business-profiles/active', { method: 'PATCH', body: { business_profile_id: id } }); }
  saveProfile(id, body) { return this.request(`/api/business-profiles/${encodeURIComponent(id)}`, { method: 'PATCH', body }); }
  saveSettings(body) { return this.request('/api/settings', { method: 'PATCH', body }); }
  client(id) { return this.request(`/api/clients/${encodeURIComponent(id)}`); }
  saveClient(id, body) { return this.request(`/api/clients/${encodeURIComponent(id)}`, { method: 'PATCH', body }); }
}
