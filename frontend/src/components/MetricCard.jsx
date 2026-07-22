import React from "react";

export const MetricCard = React.memo(function MetricCard({ label, value, hint, tone }) {
  return (
    <article className={`metric-card ${tone || ""}`}>
      <span className="metric-label">{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </article>
  );
});
