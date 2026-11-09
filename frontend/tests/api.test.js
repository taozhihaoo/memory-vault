import assert from "node:assert/strict";
import test from "node:test";

import { api } from "../src/api.js";

/** Capture fetch calls without touching the network. */
function withFetch(status, body, handler) {
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: status >= 200 && status < 300,
      status,
      statusText: "test",
      json: async () => body,
      text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
    };
  };
  return Promise.resolve(handler(calls)).finally(() => { globalThis.fetch = original; });
}

test("search strips empty filters from the query string", async () => {
  await withFetch(200, { total: 0, results: [] }, async (calls) => {
    await api.search("quantum", { limit: 30, tag: "", content_type: "", offset: undefined });
    assert.equal(calls[0].url, "/api/search?q=quantum&limit=30");
  });
});

test("content endpoint omits the query string when no limit is given", async () => {
  await withFetch(200, { content: "x" }, async (calls) => {
    await api.content(7);
    assert.equal(calls[0].url, "/api/documents/7/content");
    await api.content(7, 500);
    assert.equal(calls[1].url, "/api/documents/7/content?max_chars=500");
  });
});

test("document ids are URL-encoded", async () => {
  await withFetch(200, {}, async (calls) => {
    await api.document("a/b");
    assert.equal(calls[0].url, "/api/documents/a%2Fb");
  });
});

test("suggest encodes user input", async () => {
  await withFetch(200, { suggestions: [] }, async (calls) => {
    await api.suggest("a b&c");
    assert.match(calls[0].url, /q=a\+b%26c/);
  });
});

test("scan posts a JSON body", async () => {
  await withFetch(200, {}, async (calls) => {
    await api.scan(["/docs"]);
    assert.equal(calls[0].options.method, "POST");
    assert.equal(calls[0].options.body, JSON.stringify(["/docs"]));
  });
});

test("non-2xx responses surface the API detail", async () => {
  await withFetch(404, { detail: "document not found" }, async () => {
    await assert.rejects(() => api.document(999), /API 404: document not found/);
  });
});
