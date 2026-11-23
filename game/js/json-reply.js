// TADSDI json-reply.js: read one JSON object out of a model reply.
// Models fence the object, or write a sentence before it. Everything before
// the first brace and after the last brace is dropped. Every module that
// asks a model for JSON reads the reply through this one function.

export function extractJsonObject(text, label) {
  let body = text.trim();
  const fence = body.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fence) body = fence[1].trim();
  const start = body.indexOf('{');
  const end = body.lastIndexOf('}');
  if (start === -1 || end === -1 || end <= start) {
    throw new Error(`no JSON object found in the ${label} reply`);
  }
  return JSON.parse(body.slice(start, end + 1));
}
