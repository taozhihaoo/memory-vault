// Thin fetch wrapper around the local MemoryVault API.
// Everything talks to the same origin — no external services, ever.

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(`API ${response.status}: ${detail}`);
  }
  return response.json();
}

export const api = {
  health: () => request("/api/health"),
  stats: () => request("/api/stats"),
  documents: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
    );
    return request(`/api/documents?${query}`);
  },
  document: (id) => request(`/api/documents/${id}`),
  content: (id, maxChars) =>
    request(`/api/documents/${id}/content${maxChars ? `?max_chars=${maxChars}` : ""}`),
  history: (id) => request(`/api/documents/${id}/history`),
  related: (id, limit = 5) => request(`/api/documents/${id}/related?limit=${limit}`),
  similar: (id) => request(`/api/documents/${id}/similar`),
  tags: () => request("/api/tags"),
  search: (q, params = {}) => {
    const query = new URLSearchParams({ q, ...params });
    return request(`/api/search?${query}`);
  },
  suggest: (q) => request(`/api/suggest?q=${encodeURIComponent(q)}`),
  graph: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
    );
    return request(`/api/graph?${query}`);
  },
  neighborhood: (id, depth = 1) =>
    request(`/api/graph/neighborhood/${id}?depth=${depth}`),
  timeline: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
    );
    return request(`/api/timeline?${query}`);
  },
  events: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
    );
    return request(`/api/timeline/events?${query}`);
  },
  duplicates: () => request("/api/duplicates"),
  scan: (roots) =>
    request("/api/scan", { method: "POST", body: JSON.stringify(roots ?? null) }),
};

export function fmtBytes(n) {
  if (n === 0 || n == null) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), units.length - 1);
  return `${(n / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function fmtNumber(n) {
  return new Intl.NumberFormat().format(n ?? 0);
}

export function fmtDate(iso) {
  if (!iso) return "—";
  return iso.replace("T", " ").replace("Z", " UTC");
}
