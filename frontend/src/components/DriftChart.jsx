import React, { useMemo } from "react";

const chartItems = [
  { label: "New", color: "#9aaab1" },
  { label: "Related", color: "#2563eb" },
  { label: "Potential Conflict", color: "#dc2626" }
];

export const DriftChart = React.memo(function DriftChart({ decisions }) {
  const counts = useMemo(() => decisions.reduce((acc, decision) => {
    const label = decision.drift?.label || "New";
    acc[label] = (acc[label] || 0) + 1;
    return acc;
  }, {}), [decisions]);
  const total = chartItems.reduce((sum, item) => sum + (counts[item.label] || 0), 0);
  let offset = 25;

  return (
    <div className="chart-row">
      <div className="donut-wrap">
        <svg width="150" height="150" viewBox="0 0 42 42" role="img" aria-label="Decision drift chart">
          <circle cx="21" cy="21" r="15.915" fill="transparent" stroke="#eef2f4" strokeWidth="8" />
          {total ? chartItems.map((item) => {
            const value = counts[item.label] || 0;
            const length = (value / total) * 100;
            const segment = (
              <circle
                key={item.label}
                cx="21"
                cy="21"
                r="15.915"
                fill="transparent"
                stroke={item.color}
                strokeDasharray={`${length} ${100 - length}`}
                strokeDashoffset={offset}
                strokeWidth="8"
              />
            );
            offset -= length;
            return segment;
          }) : null}
          <text x="21" y="23" textAnchor="middle" className="donut-center">{total}</text>
        </svg>
      </div>
      <div className="legend-list">
        {chartItems.map((item) => (
          <span key={item.label}><i style={{ background: item.color }}></i>{item.label}: {counts[item.label] || 0}</span>
        ))}
      </div>
    </div>
  );
});
