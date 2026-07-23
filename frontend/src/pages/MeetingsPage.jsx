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
    <>
      <section className="meetings-toolbar panel">
        <div>
          <h3>Team Meetings Management</h3>
          <p className="muted">Search by meeting title, team, or trace id to validate what has entered the audit memory.</p>
        </div>
        <input className="compact-input" onChange={(event) => setQuery(event.target.value)} placeholder="Search meetings" value={query} />
      </section>
      <section className="panel">
        <div className="panel-header">
          <h3>Meeting Audit Queue</h3>
          <span className="muted">{meetings.length} visible</span>
        </div>
        {!meetings.length ? (
          <EmptyState title="No meetings yet" message="Upload a transcript or audio file to build meeting history." />
        ) : (
          <div className="audit-table meeting-table">
            <div className="audit-table-head">
              <span>Meeting</span><span>Team</span><span>Status</span><span>Trace</span>
            </div>
            {meetings.map((meeting) => (
              <article className="audit-table-row meeting-row" key={meeting.id}>
                <div><strong>{meeting.title}</strong><small>{formatDate(meeting.created_at)}</small></div>
                <span>{meeting.team_id}</span>
                <StatusBadge value={meeting.status} />
                <small>{meeting.trace_id}</small>
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
