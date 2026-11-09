import assert from "node:assert/strict";
import test from "node:test";

import { decodeEntities, fmtBytes, fmtDate, fmtNumber, parseHighlight } from "../src/api.js";

test("fmtBytes formats binary units and guards bad input", () => {
  assert.equal(fmtBytes(0), "0 B");
  assert.equal(fmtBytes(512), "512 B");
  assert.equal(fmtBytes(1024), "1.0 KB");
  assert.equal(fmtBytes(1024 * 1024 * 3), "3.0 MB");
  assert.equal(fmtBytes(-5), "0 B");
  assert.equal(fmtBytes(NaN), "0 B");
});

test("fmtNumber is locale aware", () => {
  assert.equal(fmtNumber(1234567), "1,234,567");
  assert.equal(fmtNumber(1234567, "zh"), "1,234,567");
  assert.equal(fmtNumber(null), "0");
});

test("fmtDate produces a readable localised timestamp", () => {
  const iso = "2026-11-09T14:30:00Z";
  assert.match(fmtDate(iso, "en"), /2026/);
  assert.match(fmtDate(iso, "zh"), /2026/);
  assert.equal(fmtDate(null), "—");
  assert.equal(fmtDate("not-a-date"), "not-a-date");
});

test("decodeEntities restores escaped document text", () => {
  assert.equal(decodeEntities("&lt;script&gt; &amp; &quot;x&quot; &#x27;y&#x27;"),
    '<script> & "x" \'y\'');
  assert.equal(decodeEntities("plain text"), "plain text");
  assert.equal(decodeEntities("&unknown;"), "&unknown;");
});

test("parseHighlight keeps marks separate from escaped text", () => {
  const segments = parseHighlight("A &lt;b&gt; <mark>secret</mark> tail");
  assert.deepEqual(segments, [
    { text: "A <b> ", mark: false },
    { text: "secret", mark: true },
    { text: " tail", mark: false },
  ]);
});

test("parseHighlight never treats document HTML as a mark", () => {
  const segments = parseHighlight("&lt;img src=x onerror=alert(1)&gt; <mark>ok</mark>");
  assert.equal(segments.filter((s) => s.mark).length, 1);
  assert.match(segments[0].text, /<img src=x onerror=alert\(1\)>/);

  // A legacy/unsafe API response is still rendered as inert text, never as a tag.
  const unsafe = parseHighlight("<script>alert(1)</script> plain");
  assert.ok(unsafe.every((s) => s.mark === false));
  assert.equal(unsafe.map((s) => s.text).join(""), "<script>alert(1)</script> plain");
});

test("parseHighlight handles empty and unmatched markers", () => {
  assert.deepEqual(parseHighlight(""), []);
  assert.deepEqual(parseHighlight("plain only"), [{ text: "plain only", mark: false }]);
  assert.deepEqual(parseHighlight("<mark>open"), [{ text: "open", mark: true }]);
});
