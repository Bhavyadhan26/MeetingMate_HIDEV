import React from "react";
import { StatusBadge } from "./StatusBadge.jsx";

export const ActionItemCard = React.memo(function ActionItemCard({ item }) {
  return (
    <article className="action-item">
      <h4>{item.task}</h4>
      <p><strong>Owner</strong> <StatusBadge value={item.owner || "Unassigned"} /></p>
      {item.deadline ? <p><strong>Deadline</strong> {item.deadline}</p> : null}
      {item.source_excerpt ? <p className="quoted">{item.source_excerpt}</p> : null}
    </article>
  );
});
