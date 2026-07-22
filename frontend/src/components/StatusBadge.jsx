import React from "react";

function token(value) {
  return String(value || "unknown").replaceAll(" ", "-").toLowerCase();
}

export const StatusBadge = React.memo(function StatusBadge({ value }) {
  return <span className={`badge ${token(value)}`}>{value || "unknown"}</span>;
});
