import React, { useEffect, useState } from "react";
import api from "./lib/api";
import useFetch from "./hooks/useFetch";
import ArticleList from "./components/ArticleList";
import ArticleModal from "./components/ArticleModal";
import {
  PieChart,
  Pie,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";

export default function App() {
  const {
    data: articles,
    loading,
    call: reloadArticles,
  } = useFetch(() => api.fetchArticles(50), [], { immediate: true });
  const [selected, setSelected] = useState(null);
  const [metrics, setMetrics] = useState({ bias: [], sentiment: [] });
  const [polling, setPolling] = useState(false);

  async function loadMetrics() {
    try {
      const m = await api.metrics();
      setMetrics(m);
    } catch (e) {
      console.error("metrics error", e);
    }
  }

  useEffect(() => {
    // initial metrics load
    loadMetrics();
    // optional poll: refresh metrics every 20s when polling enabled
    let t;
    if (polling) {
      t = setInterval(() => {
        reloadArticles();
        loadMetrics();
      }, 20000);
    }
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [polling]);

  async function handleEnrich(id) {
    try {
      await api.enrichArticle(id);
      await reloadArticles();
      await loadMetrics();
    } catch (e) {
      alert("Enrich failed: " + e.message);
    }
  }

  async function handleEnrichAsync(limit = 5) {
    try {
      await api.enrichAsync(limit);
      // optimistic: start polling for metrics
      setPolling(true);
    } catch (e) {
      alert("Failed to queue enrichment: " + e.message);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <header className="max-w-6xl mx-auto flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">NewsGuard AI — Dashboard</h1>
        <div className="flex gap-2">
          <button
            onClick={() => {
              reloadArticles();
              loadMetrics();
            }}
            className="px-3 py-2 bg-indigo-600 text-white rounded"
          >
            Refresh
          </button>
          <button
            onClick={() => handleEnrichAsync(10)}
            className="px-3 py-2 border rounded"
          >
            Run Enrich Async
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="lg:col-span-2">
          <h2 className="text-lg font-medium mb-4">
            Articles{" "}
            {loading && <span className="text-sm text-gray-500">loading…</span>}
          </h2>
          <ArticleList
            articles={articles || []}
            onEnrich={handleEnrich}
            onOpen={(a) => setSelected(a)}
          />
        </section>

        <aside className="space-y-4">
          <div className="bg-white p-4 rounded shadow">
            <h3 className="font-semibold mb-2">Bias Distribution</h3>
            <div style={{ width: "100%", height: 180 }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={metrics.bias}
                    dataKey="value"
                    nameKey="label"
                    outerRadius={60}
                    label
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-white p-4 rounded shadow">
            <h3 className="font-semibold mb-2">Sentiment</h3>
            <div style={{ width: "100%", height: 180 }}>
              <ResponsiveContainer>
                <BarChart data={metrics.sentiment}>
                  <XAxis dataKey="label" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="value" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </aside>
      </main>

      <ArticleModal
        article={selected}
        onClose={() => setSelected(null)}
        onEnrich={handleEnrich}
      />
    </div>
  );
}
