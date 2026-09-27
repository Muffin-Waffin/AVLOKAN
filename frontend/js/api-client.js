/* Shared API configuration and fetch/error handling for the existing UI. */
(function () {
  const meta = document.querySelector('meta[name="avlokan-api-base"]');
  const base = (window.AVLOKAN_API_BASE || (meta && meta.content) || 'http://127.0.0.1:8000').replace(/\/$/, '');
  window.AVLOKAN_API_BASE = base;

  function apiUrl(path) {
    return /^https?:\/\//i.test(path) ? path : base + (path.startsWith('/') ? path : '/' + path);
  }

  async function apiRequest(path, options) {
    let response;
    try {
      response = await fetch(apiUrl(path), options || {});
    } catch (error) {
      const unavailable = new Error('Backend unavailable. Start the AVLOKAN API and try again.');
      unavailable.cause = error;
      throw unavailable;
    }
    const contentType = response.headers.get('content-type') || '';
    if (!response.ok) {
      let detail = 'Request failed (' + response.status + ')';
      if (contentType.includes('application/json')) {
        try { detail = (await response.json()).detail || detail; } catch (_) { /* use status */ }
      }
      const error = new Error(detail);
      error.status = response.status;
      throw error;
    }
    if (contentType.includes('application/json')) return response.json();
    return response;
  }

  function apiJson(path, body, method) {
    return apiRequest(path, {
      method: method || 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
  }

  function apiAsset(path) { return apiUrl(path || ''); }
  function apiError(error) { return error && error.message ? error.message : 'Unexpected API error'; }

  window.apiRequest = apiRequest;
  window.apiJson = apiJson;
  window.apiAsset = apiAsset;
  window.apiError = apiError;
})();
