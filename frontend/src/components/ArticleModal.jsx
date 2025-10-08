import React from "react";

export default function ArticleModal({ article, onClose, onEnrich }) {
  if (!article) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white max-w-2xl w-full p-6 rounded shadow-lg">
        <div className="flex justify-between items-start">
          <h3 className="text-xl font-semibold">{article.title}</h3>
          <div className="flex gap-2">
            <button
              onClick={() => onEnrich(article.id)}
              className="px-3 py-1 bg-indigo-600 text-white rounded"
            >
              Analyze
            </button>
            <button onClick={onClose} className="px-3 py-1 border rounded">
              Close
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-1">
          {article.source} • {new Date(article.published_at).toLocaleString()}
        </p>
        <div className="mt-4 space-y-3">
          <p className="text-sm text-gray-700">
            {article.summary ?? article.raw_text ?? "No text available"}
          </p>
          <div className="text-sm text-gray-600">
            Sentiment: {article.sentiment ?? "—"} | Bias: {article.bias ?? "—"}
          </div>
          <a
            className="text-blue-600 text-sm"
            href={article.url}
            target="_blank"
            rel="noreferrer"
          >
            Open source article
          </a>
        </div>
      </div>
    </div>
  );
}
