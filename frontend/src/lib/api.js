const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const API_KEY = import.meta.env.VITE_API_KEY || "test123";

function headers() {
  return {
    "x-api-key": API_KEY,
    "Content-Type": "application/json",
    Accept: "application/json",
  };
}

async function fetchJson(path, opts = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    ...opts,
    headers: {
      ...headers(),
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    try {
      const json = JSON.parse(text);
      throw new Error(json.detail || json.error || text);
    } catch {
      throw new Error(text || `HTTP ${res.status}`);
    }
  }
  return res.json();
}

export default {
  fetchArticles: async (limit = 20) => fetchJson(`/news?limit=${limit}`),
  getArticle: async (id) => fetchJson(`/news/${id}`),
  enrichArticle: async (id) =>
    fetchJson(`/news/enrich/${id}`, { method: "POST" }),
  enrichAll: async (limit = 5) =>
    fetchJson(`/news/enrich_all?limit=${limit}`, { method: "POST" }),
  fetchLatest: async (q) => fetchJson(`/news/fetch?q=${encodeURIComponent(q)}`),
  enrichAsync: async (limit = 5) =>
    fetchJson(`/news/enrich_async?limit=${limit}`, { method: "POST" }),
  metrics: async () => fetchJson(`/news/metrics`),
};
