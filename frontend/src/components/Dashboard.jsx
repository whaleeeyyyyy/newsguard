import React, { useMemo } from "react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";

/*
  Note: Recharts will auto-choose colors if you don't set them.
  We will not set colors explicitly to follow your instructions.
*/

export default function Dashboard({ articles = [] }) {
  const biasCounts = useMemo(() => {
    const map = {};
    for (const a of articles) {
      const k = (a.bias || "unknown").toLowerCase();
      map[k] = (map[k] || 0) + 1;
    }
    return Object.entries(map).map(([name, value]) => ({ name, value }));
  }, [articles]);

  const sentimentCounts = useMemo(() => {
    const map = {};
    for (const a of articles) {
      const k = (a.sentiment || "UNKNOWN").toUpperCase();
      map[k] = (map[k] || 0) + 1;
    }
    return Object.entries(map).map(([name, value]) => ({ name, value }));
  }, [articles]);

  return (
    <div>
      <h3 className="font-semibold mb-2">Analytics</h3>

      <div style={{ width: "100%", height: 180 }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={biasCounts}
              dataKey="value"
              nameKey="name"
              outerRadius={60}
              label
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <div style={{ width: "100%", height: 180 }} className="mt-4">
        <ResponsiveContainer>
          <BarChart data={sentimentCounts}>
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="value" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
