// TADSDI settings.js: settings dialog + localStorage persistence.
// Schema per DESIGN.md section 5.2. Keys stay in localStorage and ride
// only in the Authorization header to the provider (D9).

import { complete } from './providers.js?v=34';

export const SETTINGS_KEY = 'tadsdi.settings.v1';
export const PROVIDER_ROLES = ['text', 'vision', 'image'];
export const PROVIDER_IDS = ['mock', 'openai', 'anthropic', 'openai-compatible'];

const DEFAULT_ROLE = { provider: 'mock', baseUrl: '', model: '', apiKey: '',
  thinkingEffort: 'default' };

// The effort vocabulary is provider-neutral and passes through verbatim on
// OpenAI-style calls (DESIGN.md 5.2). Providers and gateways add their own
// tokens over time, so the list is not a validity whitelist.
const THINKING_EFFORTS = ['off', 'default', 'minimal', 'low', 'medium',
  'high', 'xhigh', 'max', 'ultra'];

function defaultSettings() {
  return {
    roles: {
      text: { ...DEFAULT_ROLE, model: 'mock-interviewer' },
      vision: { ...DEFAULT_ROLE, model: 'mock-vision' },
      image: { ...DEFAULT_ROLE, model: 'mock-image' },
    },
    preferences: {
      helpMode: 'learning',   // 'learning' | 'testing'
      constraintMode: 'unconstrained',
      timerMinutes: 0,        // 0 = off
      showHowToAtStart: true, // false after the player ticks the box in how to play
    },
  };
}

export function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return defaultSettings();
    const data = JSON.parse(raw);
    const defaults = defaultSettings();
    const roles = {};
    for (const role of PROVIDER_ROLES) {
      roles[role] = { ...defaults.roles[role], ...(data.roles && data.roles[role]) };
    }
    return { roles, preferences: { ...defaults.preferences, ...(data.preferences || {}) } };
  } catch {
    return defaultSettings();
  }
}

export function saveSettings(settings) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}

// Whether "How to play" opens when the game loads. Only the value false
// stops it, so a stored value of another shape still opens the dialog.
export function howToAtStart() {
  return loadSettings().preferences.showHowToAtStart !== false;
}

export function setHowToAtStart(show) {
  const settings = loadSettings();
  settings.preferences.showHowToAtStart = show;
  saveSettings(settings);
}

function rowTemplate(role) {
  const options = PROVIDER_IDS
    .map((id) => `<option value="${id}">${id}</option>`)
    .join('');
  const efforts = THINKING_EFFORTS
    .map((e) => `<option value="${e}">${e}</option>`)
    .join('');
  return `
    <tr data-role="${role}">
      <th scope="row">${role}</th>
      <td><select class="provider-id">${options}</select></td>
      <td><input class="base-url" type="text" placeholder="https://..."></td>
      <td><input class="model" type="text"></td>
      <td><input class="api-key" type="password" placeholder="optional"></td>
      <td><select class="thinking-effort">${efforts}</select></td>
      <td>
        <button type="button" class="test-connection">Test connection</button>
        <div class="test-result" role="status"></div>
      </td>
    </tr>`;
}

function fillRow(tbody, role, config) {
  const row = tbody.querySelector(`tr[data-role="${role}"]`);
  row.querySelector('select.provider-id').value = config.provider;
  row.querySelector('input.base-url').value = config.baseUrl || '';
  row.querySelector('input.model').value = config.model || '';
  row.querySelector('input.api-key').value = config.apiKey || '';
  row.querySelector('select.thinking-effort').value = config.thinkingEffort || 'default';
}

function collectRow(row) {
  return {
    provider: row.querySelector('select.provider-id').value,
    baseUrl: row.querySelector('input.base-url').value.trim(),
    model: row.querySelector('input.model').value.trim(),
    apiKey: row.querySelector('input.api-key').value,
    thinkingEffort: row.querySelector('select.thinking-effort').value || 'default',
  };
}

async function testRowConnection(row, setMessage) {
  const result = row.querySelector('.test-result');
  result.className = 'test-result';
  result.textContent = 'Testing...';
  const config = collectRow(row);
  try {
    const reply = await complete('text', [{ role: 'user', content: 'ping' }], {
      overrideConfig: config,
      purpose: 'test_connection',
    });
    result.className = 'test-result ok';
    result.textContent = `ok: ${reply}`;
  } catch (err) {
    result.className = 'test-result fail';
    result.textContent = `fail: ${err.message}`;
  }
}

// The thinking effort rides on each role config (DESIGN.md 5.2). The old
// context-window field is gone: the game default of 32000 tokens always
// applies unless a stored settings blob still carries contextTokens.
export function initSettings() {
  const dialog = document.getElementById('settings-dialog');
  const tbody = dialog.querySelector('#provider-rows tbody');
  tbody.innerHTML = PROVIDER_ROLES.map(rowTemplate).join('');

  const fillFromStorage = () => {
    const settings = loadSettings();
    for (const role of PROVIDER_ROLES) fillRow(tbody, role, settings.roles[role]);
  };

  document.getElementById('open-settings').addEventListener('click', () => {
    fillFromStorage();
    dialog.querySelector('#settings-message').textContent = '';
    dialog.showModal();
  });
  document.getElementById('settings-close').addEventListener('click', () => dialog.close());

  document.getElementById('settings-save').addEventListener('click', () => {
    // The rows replace the roles. The preferences stay as they are stored.
    const settings = loadSettings();
    for (const row of tbody.querySelectorAll('tr[data-role]')) {
      settings.roles[row.dataset.role] = collectRow(row);
    }
    saveSettings(settings);
    dialog.querySelector('#settings-message').textContent = 'Saved to localStorage.';
  });

  for (const row of tbody.querySelectorAll('tr[data-role]')) {
    row.querySelector('button.test-connection').addEventListener('click', () => {
      testRowConnection(row, dialog.querySelector('#settings-message'));
    });
  }
}
