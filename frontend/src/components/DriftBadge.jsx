import React from "react";
import { StatusBadge } from "./StatusBadge.jsx";

export const DriftBadge = React.memo(function DriftBadge({ value }) {
  return <StatusBadge value={value || "New"} />;
});
