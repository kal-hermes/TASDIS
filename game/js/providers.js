// TADSDI providers.js: one provider interface per DESIGN.md section 10.
// complete(role, messages, options) -> Promise<string>
// completeStream(role, messages, onChunk, options) -> Promise<string>
// Adapters: mock, openai, anthropic, openai-compatible.
// A later Bifrost router swap touches only this module.
//
// Errors: adapters throw typed low-level errors (NetworkError, TimeoutError,
// HttpError). The public interface turns every failure into one readable
// message with a next step, so no caller parses a raw failure.

import { loadSettings } from './settings.js?v=36';

const PROVIDER_NAMES = {
  mock: 'mock',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  'openai-compatible': 'OpenAI-compatible',
};

const DEFAULT_BASES = {
  openai: 'https://api.openai.com/v1',
  anthropic: 'https://api.anthropic.com',
};

// ---- typed errors -----------------------------------------------------

class NetworkError extends Error {
  constructor(detail) {
    super(`request failed before an HTTP answer: ${detail}`);
    this.kind = 'network';
  }
}

class TimeoutError extends Error {
  constructor() {
    super('the request timed out');
    this.kind = 'timeout';
  }
}

class HttpError extends Error {
  constructor(status, body) {
    super(`HTTP ${status}: ${String(body).slice(0, 300)}`);
    this.kind = 'http';
    this.status = status;
    this.body = String(body).slice(0, 300);
  }
}

class ConfigError extends Error {
  constructor(message) {
    super(message);
    this.kind = 'config';
  }
}

class EmptyReplyError extends Error {
  constructor() {
    super('empty reply');
    this.kind = 'empty';
  }
}

export const ProviderErrors = {
  NetworkError, TimeoutError, HttpError, ConfigError, EmptyReplyError,
};

// Two limits keep a stalled provider from hanging the game: one on the wait
// for the first byte, one on the wait between two stream chunks.
const TIMEOUTS = { requestMs: 60000, idleMs: 60000 };

export function setProviderTimeouts(partial) {
  Object.assign(TIMEOUTS, partial);
}

function httpAdvice(name, status, body) {
  if (status === 401 || status === 403) {
    return `${name} rejected the request (HTTP ${status}). Check the API key in ` +
      'Settings; leave it empty if your endpoint needs none.';
  }
  if (status === 404) {
    return `${name} returned HTTP 404. Check the Base URL and the model name in Settings.`;
  }
  if (status === 429) {
    return `${name} rate-limited the request (HTTP 429). Wait a moment, then retry.`;
  }
  if (status >= 500) {
    return `${name} had a server problem (HTTP ${status}): ${body} Retry in a moment.`;
  }
  return `${name} returned HTTP ${status}: ${body}`;
}

// One message builder per error kind. Each names the next step.
const MESSAGES = {
  config: (err) => err.message,
  network: (name, err) => `${name} request failed before an HTTP answer (network or CORS). ` +
    `Check the provider Base URL in Settings. Original error: ${err.message}`,
  timeout: (name) => `${name} did not answer within ${Math.round(TIMEOUTS.requestMs / 1000)} s. ` +
    'The request was stopped. Retry, or select a faster model in Settings.',
  http: (name, err) => httpAdvice(name, err.status, err.body),
  empty: (name) => `${name} returned an empty reply. Retry.`,
};

// Turns any failure into one readable Error with a next step. An error that
// is already described passes through unchanged.
export function describeProviderError(err, providerName) {
  if (err && err.described) return err;
  const kind = (err && err.kind) || 'unknown';
  const build = MESSAGES[kind];
  const described = new Error(build
    ? build(providerName, err)
    : `${providerName} call failed: ${err && err.message}`);
  described.kind = kind;
  described.cause = err;
  described.described = true;
  return described;
}

// ---- HTTP helpers -----------------------------------------------------

async function fetchWithTimeout(url, init) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUTS.requestMs);
  let response;
  try {
    response = await fetch(url, { ...init, signal: controller.signal });
  } catch (err) {
    if (controller.signal.aborted) throw new TimeoutError();
    throw new NetworkError(err.message);
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new HttpError(response.status, body);
  }
  return { response, controller };
}

async function fetchJson(url, init) {
  const { response } = await fetchWithTimeout(url, init);
  return response.json();
}

// Rejects with TimeoutError when the stream sends nothing for idleMs.
function withIdleTimeout(readOnce, controller) {
  let timer;
  const guard = new Promise((_, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      reject(new TimeoutError());
    }, TIMEOUTS.idleMs);
  });
  const guarded = readOnce().catch((err) => {
    if (controller.signal.aborted) throw new TimeoutError();
    throw new NetworkError(err.message);
  });
  return Promise.race([guarded, guard]).finally(() => clearTimeout(timer));
}

// ---- SSE helpers ------------------------------------------------------

async function streamSse(url, init, onDelta) {
  const { response, controller } = await fetchWithTimeout(url, init);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let full = '';
  for (;;) {
    const { done, value } = await withIdleTimeout(() => reader.read(), controller);
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data:')) continue;
      const payload = trimmed.slice(5).trim();
      if (payload === '[DONE]') continue;
      let event;
      try {
        event = JSON.parse(payload);
      } catch {
        continue;
      }
      const delta = onDelta(event);
      if (delta) {
        full += delta;
      }
    }
  }
  return full;
}

// ---- request builders -------------------------------------------------

// One place builds the OpenAI-shape request for both call styles. An empty
// API key sends no Authorization header: a gateway or a local endpoint can
// need none.
// The thinking-effort setting maps to request parameters in game code
// (DESIGN.md 5.2). The vocabulary is provider-neutral and passes through:
// 'default' omits the field (the provider picks; defaults are
// model-dependent), 'off' means reasoning disabled ('none' on OpenAI-style
// calls, field omitted on Anthropic-style calls where classic thinking is
// opt-in), and the ladder values ride OpenAI-style calls verbatim and map
// to thinking budgets on Anthropic-style calls. The mock carries nothing.
const ANTHROPIC_BUDGETS = { minimal: 1024, low: 2048, medium: 8192,
  high: 16384, xhigh: 32768, max: 65536, ultra: 131072 };

export function thinkingParams(config) {
  const effort = config && config.thinkingEffort;
  if (!effort || effort === 'default') return {};
  if (config.provider === 'anthropic') {
    const budget = ANTHROPIC_BUDGETS[effort];
    if (!budget) return {};
    return { thinking: { type: 'enabled', budget_tokens: budget },
      max_tokens: budget + 1024 };
  }
  if (config.provider === 'openai' || config.provider === 'openai-compatible') {
    return { reasoning_effort: effort === 'off' ? 'none' : effort };
  }
  return {};
}

function openAiRequest(config, messages, stream) {
  const base = (config.baseUrl || DEFAULT_BASES.openai).replace(/\/+$/, '');
  const headers = { 'Content-Type': 'application/json' };
  if (config.apiKey) headers.Authorization = `Bearer ${config.apiKey}`;
  return {
    url: `${base}/chat/completions`,
    init: {
      method: 'POST',
      headers,
      body: JSON.stringify({ model: config.model, messages, stream,
        ...thinkingParams(config) }),
    },
  };
}

function anthropicParts(config, messages) {
  const base = (config.baseUrl || DEFAULT_BASES.anthropic).replace(/\/+$/, '');
  const system = messages.filter((m) => m.role === 'system').map((m) => m.content).join('\n');
  const turns = messages.filter((m) => m.role !== 'system');
  return { base, system, turns };
}

function anthropicRequest(config, messages, stream) {
  const { base, system, turns } = anthropicParts(config, messages);
  const headers = {
    'Content-Type': 'application/json',
    'anthropic-version': '2023-06-01',
    'anthropic-dangerous-direct-browser-access': 'true',
  };
  if (config.apiKey) headers['x-api-key'] = config.apiKey;
  return {
    url: `${base}/v1/messages`,
    init: {
      method: 'POST',
      headers,
      body: JSON.stringify({
        model: config.model,
        max_tokens: 2048,
        ...thinkingParams(config),
        ...(stream ? { stream: true } : {}),
        messages: turns,
        ...(system ? { system } : {}),
      }),
    },
  };
}

function openAiDelta(event) {
  return event.choices && event.choices[0] &&
    event.choices[0].delta && event.choices[0].delta.content;
}

function anthropicDelta(event) {
  return event.type === 'content_block_delta' && event.delta && event.delta.text;
}

// ---- adapters ---------------------------------------------------------

const ADAPTERS = {
  async mock(config, messages, options) {
    const script = await loadMockScript(config);
    const text = pickMockReply(script, options);
    await new Promise((resolve) => setTimeout(resolve, options.delayMs ?? 150));
    return text;
  },

  async openai(config, messages) {
    const { url, init } = openAiRequest(config, messages, false);
    const data = await fetchJson(url, init);
    return data.choices[0].message.content;
  },

  async 'openai-compatible'(config, messages) {
    const { url, init } = openAiRequest(config, messages, false);
    const data = await fetchJson(url, init);
    return data.choices[0].message.content;
  },

  async anthropic(config, messages) {
    const { url, init } = anthropicRequest(config, messages, false);
    const data = await fetchJson(url, init);
    return data.content.map((block) => block.text || '').join('');
  },
};

const STREAMS = {
  async mock(config, messages, onChunk, options) {
    const script = await loadMockScript(config);
    const text = pickMockReply(script, options);
    const words = text.split(/(\s+)/);
    let full = '';
    for (const word of words) {
      await new Promise((resolve) => setTimeout(resolve, options.chunkDelayMs ?? 20));
      onChunk(word);
      full += word;
    }
    return full;
  },

  openai(config, messages, onChunk) {
    const { url, init } = openAiRequest(config, messages, true);
    return streamSse(url, init, (event) => {
      const delta = openAiDelta(event);
      if (delta) onChunk(delta);
      return delta;
    });
  },

  'openai-compatible'(config, messages, onChunk) {
    return STREAMS.openai(config, messages, onChunk);
  },

  anthropic(config, messages, onChunk) {
    const { url, init } = anthropicRequest(config, messages, true);
    return streamSse(url, init, (event) => {
      const delta = anthropicDelta(event);
      if (delta) onChunk(delta);
      return delta;
    });
  },
};

// ---- mock script and test hooks ---------------------------------------

let mockScriptCache = null;
async function loadMockScript(config) {
  if (mockScriptCache) return mockScriptCache;
  const base = config.baseUrl || new URL('.', import.meta.url).href;
  const scriptUrl = new URL('prompts/mock-script.json?v=36', base).href;
  mockScriptCache = await fetchJson(scriptUrl, {});
  return mockScriptCache;
}

const mockCounters = new Map();
const helpLadder = new Map();
let graderQueue = [];
let checkerQueue = [];
let faultQueue = [];

// Test hook: script the grader reply sequence (names of mock-script keys).
export function setMockGraderQueue(entries) {
  graderQueue = [...entries];
}

// Test hook: script the reveal checker's replies (raw JSON strings).
export function setMockCheckerQueue(entries) {
  checkerQueue = [...entries];
}

// Test hook: make the next mock calls fail like a real provider would.
// Entries: 'network', 'timeout', 'empty', 'http:500', or
// {kind, status, body, purpose}. A fault with a purpose fails only a call
// with that purpose.
export function setMockFaultQueue(entries) {
  faultQueue = [...entries];
}

// The context window of the text model in tokens, from Settings. 0 means the
// game assumes its own default.
export function textContextTokens() {
  const text = loadSettings().roles && loadSettings().roles.text;
  return (text && Number(text.contextTokens)) || 0;
}

function normalizeFault(entry) {
  if (typeof entry !== 'string') return entry;
  if (entry.startsWith('http:')) return { kind: 'http', status: Number(entry.slice(5)) };
  return { kind: entry };
}

// Returns the reply text for a mock fault, or throws the typed error a
// real adapter would throw for the same failure.
function mockFaultResult(entry) {
  const fault = normalizeFault(entry);
  switch (fault.kind) {
    case 'empty':
      return '';
    case 'network':
      throw new NetworkError(fault.detail || 'Failed to fetch');
    case 'timeout':
      throw new TimeoutError();
    case 'http':
      throw new HttpError(fault.status, fault.body || 'injected fault');
    default:
      throw new Error(`unknown mock fault: ${JSON.stringify(entry)}`);
  }
}

// The next queued fault that may fail this call. A fault with a purpose
// fails only a call with that purpose.
function takeFault(config, options) {
  if (config.provider !== 'mock') return null;
  const index = faultQueue.findIndex((entry) => {
    const purpose = normalizeFault(entry).purpose;
    return purpose === undefined || purpose === options.purpose;
  });
  return index === -1 ? null : faultQueue.splice(index, 1)[0];
}

// The interview turns play in order and hold on the last one.
function mockInterviewTurn(script) {
  const turns = script.interview;
  const index = mockCounters.get('interview') || 0;
  mockCounters.set('interview', Math.min(index + 1, turns.length - 1));
  return turns[index].text;
}

// The help ladder climbs one rung per request and holds on the top rung.
// A refusal is the answer in testing mode.
function mockHelp(script, options) {
  if (options.helpRequest === 'refusal') return script.help.refusal;
  const rungs = script.help.ladder;
  const rung = Math.min(helpLadder.get('stage') || 0, rungs.length - 1);
  helpLadder.set('stage', rung + 1);
  return rungs[rung];
}

// A final grade comes from the grader queue, so a test can script a bad
// reply. A progress grade has one fixed reply.
function mockGrade(script, options) {
  if (options.purpose === 'grade_mid') return JSON.stringify(script.midgrade);
  const key = graderQueue.length > 0 ? graderQueue.shift() : 'grade';
  return JSON.stringify(script[key]);
}

// The reveal checker's reply comes from the checker queue as a raw JSON
// string, so a test can script what the audit found. The default finds
// nothing.
function mockCheckerReply() {
  return checkerQueue.length > 0 ? checkerQueue.shift() : '{"revealed": []}';
}

// One reply rule per call purpose. A string rule is a key of the script.
// Every other purpose is an interview turn.
const MOCK_RULES = {
  test_connection: 'test_connection',
  summarize: (script) => JSON.stringify(script.summarize),
  briefing: 'briefing',
  wrapup: 'wrapup',
  grade: mockGrade,
  grade_mid: mockGrade,
  help: mockHelp,
  check_reveals: mockCheckerReply,
};

function pickMockReply(script, options) {
  const rule = MOCK_RULES[options.purpose] || mockInterviewTurn;
  return typeof rule === 'string' ? script[rule] : rule(script, options);
}

export function resetMockState() {
  mockCounters.clear();
  helpLadder.clear();
  graderQueue = [];
  checkerQueue = [];
  mockScriptCache = null;
}

// ---- public interface -------------------------------------------------

export function validateConfig(role, config) {
  if (!config) {
    throw new ConfigError(`No provider configured for the ${role} role. Open Settings.`);
  }
  if (!ADAPTERS[config.provider]) {
    throw new ConfigError(`Unknown provider "${config.provider}" for the ${role} role. Open Settings.`);
  }
  if (config.provider === 'mock') return config;
  const name = PROVIDER_NAMES[config.provider];
  // The API key is optional: a gateway or a local endpoint can need none.
  // An empty key sends the call without an auth header.
  if (!config.model) {
    throw new ConfigError(`No model name set for the ${role} role (${name}). Add one in Settings.`);
  }
  if (config.provider === 'openai-compatible' && !config.baseUrl) {
    throw new ConfigError(`The ${name} provider needs a Base URL in Settings.`);
  }
  return config;
}

function resolveConfig(role, options) {
  return options.overrideConfig ||
    (loadSettings().roles && loadSettings().roles[role]);
}

function requireText(text) {
  if (typeof text !== 'string' || text.trim() === '') {
    throw new EmptyReplyError();
  }
  return text;
}

// One entry for both call styles: Settings validation, the fault hook for
// the mock, an empty-reply check, and the readable error mapping.
async function runProvider(role, options, call) {
  const config = validateConfig(role, resolveConfig(role, options));
  const name = PROVIDER_NAMES[config.provider];
  try {
    const fault = takeFault(config, options);
    const text = fault !== null ? mockFaultResult(fault) : await call(config);
    return requireText(text);
  } catch (err) {
    throw describeProviderError(err, name);
  }
}

export async function complete(role, messages, options = {}) {
  return runProvider(role, options, (config) =>
    ADAPTERS[config.provider](config, messages, { ...options, role }));
}

export async function completeStream(role, messages, onChunk, options = {}) {
  return runProvider(role, options, (config) =>
    STREAMS[config.provider](config, messages, onChunk, { ...options, role }));
}
