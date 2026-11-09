// Thin fetch wrapper around the local MemoryVault API.
// Everything talks to the same origin — no external services, ever.

function toQuery(params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  }
  return query.toString();
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: options.body ? { "Content-Type": "application/json" } : undefined,
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    let message = detail;
    try {
      const parsed = JSON.parse(detail);
      message = parsed.detail || parsed.message || detail;
    } catch {
      /* plain-text error body is fine */
    }
    throw new Error(`API ${response.status}: ${message}`);
  }
  return response.json();
}

export const api = {
  health: () => request("/api/health"),
  stats: () => request("/api/stats"),
  documents: (params = {}) => request(`/api/documents?${toQuery(params)}`),
  document: (id) => request(`/api/documents/${encodeURIComponent(id)}`),
  content: (id, maxChars) => {
    const query = toQuery({ max_chars: maxChars });
    return request(
      `/api/documents/${encodeURIComponent(id)}/content${query ? `?${query}` : ""}`
    );
  },
  history: (id) => request(`/api/documents/${encodeURIComponent(id)}/history`),
  related: (id, limit = 5) =>
    request(`/api/documents/${encodeURIComponent(id)}/related?${toQuery({ limit })}`),
  similar: (id) => request(`/api/documents/${encodeURIComponent(id)}/similar`),
  tags: () => request("/api/tags"),
  search: (q, params = {}) => request(`/api/search?${toQuery({ q, ...params })}`),
  suggest: (q) => request(`/api/suggest?${toQuery({ q })}`),
  graph: (params = {}) => request(`/api/graph?${toQuery(params)}`),
  neighborhood: (id, depth = 1) =>
    request(`/api/graph/neighborhood/${encodeURIComponent(id)}?${toQuery({ depth })}`),
  timeline: (params = {}) => request(`/api/timeline?${toQuery(params)}`),
  events: (params = {}) => request(`/api/timeline/events?${toQuery(params)}`),
  duplicates: () => request("/api/duplicates"),
  scan: (roots) =>
    request("/api/scan", { method: "POST", body: JSON.stringify(roots ?? null) }),
};

// ------------------------------------------------------------------ formatting
export function fmtBytes(n) {
  if (!Number.isFinite(n) || n <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), units.length - 1);
  return `${(n / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function fmtNumber(n, lang = "en") {
  return new Intl.NumberFormat(lang === "zh" ? "zh-CN" : "en-US").format(n ?? 0);
}

export function fmtDate(iso, lang = "en") {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso.replace("T", " ").replace("Z", " UTC");
  return new Intl.DateTimeFormat(lang === "zh" ? "zh-CN" : "en-US", {
    year: "numeric", month: "short", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(date);
}

// --------------------------------------------------------- safe highlighting
const ENTITIES = {
  amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: "\u00a0",
};

/** Decode the HTML entities produced by the API's escaping layer. */
export function decodeEntities(text) {
  return String(text).replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (full, code) => {
    if (code[0] === "#") {
      const hex = code[1] === "x" || code[1] === "X";
      const value = parseInt(hex ? code.slice(2) : code.slice(1), hex ? 16 : 10);
      if (Number.isFinite(value) && value >= 0 && value <= 0x10ffff) {
        try { return String.fromCodePoint(value); } catch { return full; }
      }
      return full;
    }
    return ENTITIES[code.toLowerCase()] ?? full;
  });
}

/**
 * Split an API highlight string into plain-text segments.
 *
 * The backend HTML-escapes all document text and only inserts <mark> tags.
 * We never use dangerouslySetInnerHTML: everything is rendered as React text
 * nodes, so even a malformed/legacy API response cannot inject markup.
 */
export function parseHighlight(html = "") {
  const segments = [];
  const token = /<\/?mark>/gi;
  let marked = false;
  let last = 0;
  let match;
  while ((match = token.exec(html)) !== null) {
    if (match.index > last) {
      segments.push({ text: decodeEntities(html.slice(last, match.index)), mark: marked });
    }
    marked = match[0].toLowerCase() === "<mark>";
    last = match.index + match[0].length;
  }
  if (last < html.length) {
    segments.push({ text: decodeEntities(html.slice(last)), mark: marked });
  }
  return segments;
}
