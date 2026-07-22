import React from "react";
import { EmptyState } from "./EmptyState.jsx";

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export const ActivityFeed = React.memo(function ActivityFeed({ activities }) {
  if (!activities.length) {
    return <EmptyState title="No activity yet" message="Process a meeting to start building the activity feed." />;
  }

  return (
    <div className="activity-feed">
      {activities.map((item) => (
        <article className="activity-item" key={item.id}>
          <span>{item.type}</span>
          <div>
            <strong>{item.text}</strong>
            <small>{item.detail} | {formatDate(item.at)}</small>
          </div>
        </article>
      ))}
    </div>
  );
});
