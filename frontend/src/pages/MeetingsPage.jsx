import { useMemo, useState } from "react";
import { EmptyState } from "../components/EmptyState.jsx";
import { StatusBadge } from "../components/StatusBadge.jsx";

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export default function MeetingsPage({ appState }) {
  const [query, setQuery] = useState("");
  const meetings = useMemo(() => {
    const normalized = query.toLowerCase();
    return appState.meetings.filter((meeting) => `${meeting.title} ${meeting.team_id} ${meeting.trace_id}`.toLowerCase().includes(normalized));
  }, [appState.meetings, query]);

  return (
    <section className="panel">
      <div className="panel-header">
        <h3>Meeting History</h3>
        <input className="compact-input" onChange={(event) => setQuery(event.target.value)} placeholder="Search meetings" value={query} />
      </div>
      {!meetings.length ? (
        <EmptyState title="No meetings yet" message="Upload a transcript or audio file to build meeting history." />
      ) : (
        <div className="table-list">
          {meetings.map((meeting) => (
            <article className="table-row" key={meeting.id}>
              <div>
                <strong>{meeting.title}</strong>
                <small>{meeting.team_id} | {formatDate(meeting.created_at)}</small>
              </div>
              <StatusBadge value={meeting.status} />
              <small>{meeting.trace_id}</small>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
