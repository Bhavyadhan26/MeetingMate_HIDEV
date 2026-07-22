import React from "react";
import { StatusBadge } from "./StatusBadge.jsx";

export const CitationList = React.memo(function CitationList({ citations }) {
  if (!citations?.length) return null;
  return (
    <div className="citation-list">
      {citations.map((citation, index) => (
        <article className="citation-card" key={citation.id || citation.decision_id || index}>
          <div className="inline-actions">
            <StatusBadge value={citation.status || "cited"} />
            {citation.score ? <small>score {Number(citation.score).toFixed(2)}</small> : null}
          </div>
          <p>{citation.text || citation.source_excerpt}</p>
          {citation.id || citation.decision_id ? <small>{citation.id || citation.decision_id}</small> : null}
        </article>
      ))}
    </div>
  );
});
