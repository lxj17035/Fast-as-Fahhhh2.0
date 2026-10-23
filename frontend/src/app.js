import { Api } from './api.js';
import { API_BASE_URL } from '../config.js';

const api = new Api(API_BASE_URL);
document.querySelector('#app').innerHTML = `<main class="foundation"><div class="brand-mark">Q</div><p class="eyebrow">YOUR ENQUIRY WORKSPACE</p><h1>Less busywork.<br>More business.</h1><p>QuoteFlow connects enquiries, quotations, and PM review.</p><p id="connection" role="status">Connecting to the local API…</p></main>`;
api.health().then(() => { document.querySelector('#connection').textContent = 'Backend connected. Workspace implementation in progress.'; })
  .catch(error => { document.querySelector('#connection').textContent = error.message; });
