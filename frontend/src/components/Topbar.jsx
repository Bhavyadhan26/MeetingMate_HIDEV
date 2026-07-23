import React from "react";
import { useLocation } from "react-router-dom";

const titles = {
  "/": ["Auditor Dashboard", "Operational command center"],
  "/upload": ["AI Meeting Intelligence PRD", "Meeting ingestion workflow"],
  "/meetings": ["Team Meetings Management", "Meeting history and ownership"],
  "/decisions": ["Meeting Details & Audit Report", "Decisions, evidence, and drift"],
  "/memory": ["Memory Ledger Search", "Semantic recall and pre-meeting briefs"],
  "/conflicts": ["Conflict Resolution Workspace", "Review, resolve, and escalate"],
  "/settings": ["PII Redaction Settings", "Privacy rules and storage controls"],
  "/design-system": ["Design System", "Auditor interface reference"]
};

export const Topbar = React.memo(function Topbar({ auth, status }) {
  const location = useLocation();
  const [label, title] = titles[location.pathname] || titles["/"];
  return (
    <header className="topbar">
      <div className="topbar-title">
        <h2>Organizational Memory</h2>
        <span>{label} / {title}</span>
      </div>
      <div className="topbar-search">
        <span className="material-symbols-outlined">search</span>
        <input placeholder="QUERY MEMORY LEDGER..." type="text" />
      </div>
      <div className="auth-row">
        {auth?.enabled && !auth.authenticated ? <button className="secondary-button" type="button" onClick={auth.login}>Log In</button> : null}
        {auth?.enabled && auth.authenticated ? <button className="secondary-button" type="button" onClick={auth.logout}>Log Out</button> : null}
        <button className="icon-button" type="button"><span className="material-symbols-outlined">notifications</span></button>
        <button className="icon-button" type="button"><span className="material-symbols-outlined">security</span></button>
        <button className="icon-button" type="button"><span className="material-symbols-outlined">help_center</span></button>
        <span className="status">{auth?.label || "Auth optional"}</span>
        <span className="status">{status}</span>
      </div>
    </header>
  );
});
