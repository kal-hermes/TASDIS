// TADSDI problems.js: problem bank loader (DESIGN.md 5.1).

import { validateBrief } from './prompts/brief.js?v=34';

export const PROBLEM_SLUGS = [
  'url-shortener',
  'rate-limiter',
  'news-feed',
  'chat',
  'autocomplete',
  'web-crawler',
  'unique-id-generator',
  'notification-system',
];

const cache = new Map();

// The bank never feeds the interviewer a malformed prep pack: a problem
// that carries one gets it validated here, at load time (DESIGN.md 7).
export async function loadProblem(slug) {
  if (cache.has(slug)) return cache.get(slug);
  const url = new URL(`problems/${slug}.json?v=34`, import.meta.url).href;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`problem bank entry not found: ${slug} (HTTP ${response.status})`);
  }
  const problem = await response.json();
  validateBrief(problem);
  cache.set(slug, problem);
  return problem;
}

export async function loadProblems() {
  const entries = await Promise.all(PROBLEM_SLUGS.map(async (slug) => {
    try {
      return [slug, await loadProblem(slug)];
    } catch {
      return [slug, null];
    }
  }));
  return new Map(entries);
}
