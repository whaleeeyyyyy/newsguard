import React from "react";

export default function ArticleCard({ article, onEnrich, onOpen }) {
  const badge = (text) => (
    <span className="text-xs px-2 py-0.5 border rounded-full">{text}</span>
  );

  return (
    <article className="bg-white p-4 rounded shadow hover:shadow-md transition">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="text-md font-semibold cursor-pointer" onClick={onOpen}>
            {article.title}
          </h3>
          <div className="text-xs text-gray-500 mt-1">
            {article.source} • {new Date(article.published_at).toLocaleString()}
          </div>
        </div>
        <div className="ml-3 flex flex-col items-end gap-2">
          <button
            onClick={onEnrich}
            className="text-xs px-2 py-1 border rounded"
          >
            Analyze
          </button>
          <a
            href={article.url}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-blue-600"
          >
            Source
          </a>
        </div>
      </div>

      <div className="mt-3 text-sm text-gray-700">
        <p>
          {article.summary ??
            (article.raw_text
              ? article.raw_text.slice(0, 200) + "…"
              : "No text available")}
        </p>
      </div>

      <div className="mt-3 flex items-center gap-2">
        {article.sentiment ? (
          badge(article.sentiment)
        ) : (
          <span className="text-xs text-gray-400">sentiment: —</span>
        )}
        {article.bias ? (
          badge(article.bias)
        ) : (
          <span className="text-xs text-gray-400">bias: —</span>
        )}
      </div>
    </article>
  );
}
