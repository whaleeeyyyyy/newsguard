import React from "react";
import ArticleCard from "./ArticleCard";

export default function ArticleList({ articles = [], onEnrich, onOpen }) {
  return (
    <div className="space-y-3">
      {articles.length === 0 ? (
        <div className="p-6 bg-white rounded shadow text-sm text-gray-500">
          No articles yet — click “Fetch latest”.
        </div>
      ) : (
        articles.map((a) => (
          <ArticleCard
            key={a.id}
            article={a}
            onEnrich={() => onEnrich(a.id)}
            onOpen={() => onOpen(a)}
          />
        ))
      )}
    </div>
  );
}
