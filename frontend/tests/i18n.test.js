import assert from "node:assert/strict";
import test from "node:test";

import { DICT, LANGUAGES, detectLanguage, missingKeys, normalizeLang, t } from "../src/i18n.js";

test("every language has the same translation keys", () => {
  for (const source of LANGUAGES) {
    for (const target of LANGUAGES) {
      assert.deepEqual(missingKeys(source, target), [], `${source} -> ${target}`);
    }
  }
});

test("no translation is empty and interpolation placeholders match", () => {
  for (const [lang, table] of Object.entries(DICT)) {
    for (const [key, value] of Object.entries(table)) {
      assert.ok(value.trim().length > 0, `${lang}:${key} is empty`);
      const vars = [...value.matchAll(/\{(\w+)\}/g)].map((m) => m[1]);
      const counterpart = DICT.en[key] || "";
      const enVars = [...counterpart.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
      assert.deepEqual([...vars].sort(), enVars, `${lang}:${key} placeholders differ`);
    }
  }
});

test("t interpolates variables and falls back to English", () => {
  assert.equal(t("en", "search.results", { n: 3, unit: "results", ms: 1.2 }), "3 results · 1.2 ms");
  assert.equal(t("zh", "search.results", { n: 3, unit: "条结果", ms: 1.2 }), "3 条结果 · 1.2 毫秒");
  assert.equal(t("zh", "no.such.key"), "no.such.key");
  assert.equal(t("fr", "nav.search"), "Search");
});

test("language detection priority: URL > storage > browser > English", () => {
  assert.equal(detectLanguage({ search: "?lang=zh", stored: "en", browser: "en-US" }), "zh");
  assert.equal(detectLanguage({ search: "", stored: "zh", browser: "en-US" }), "zh");
  assert.equal(detectLanguage({ search: "", stored: "", browser: "zh-CN" }), "zh");
  assert.equal(detectLanguage({}), "en");
  assert.equal(detectLanguage({ search: "?lang=bogus", browser: "fr-FR" }), "en");
});

test("normalizeLang handles common aliases", () => {
  assert.equal(normalizeLang("zh-CN"), "zh");
  assert.equal(normalizeLang("zh_Hans"), "zh");
  assert.equal(normalizeLang("EN-us"), "en");
  assert.equal(normalizeLang("中文"), null);
});
