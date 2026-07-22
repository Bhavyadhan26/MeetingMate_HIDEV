import React from "react";
import { useLocation } from "react-router-dom";

const titles = {
  "/": ["Dashboard", "Command center"],
  "/upload": ["Upload", "New meeting"],
  "/meetings": ["Meetings", "Meeting history"],
  "/decisions": ["Decisions", "Decision ledger"],
  "/memory": ["Memory", "Recall and briefs"],
  "/conflicts": ["Conflicts", "Conflict audit center"],
  "/settings": ["Settings", "Team and storage"]
};

export const Topbar = React.memo(function Topbar({ auth, status }) {
  const location = useLocation();
  const [label, title] = titles[location.pathname] || titles["/"];
  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">{label}</p>
        <h2>{title}</h2>
      </div>
      <div className="auth-row">
        {auth?.enabled && !auth.authenticated ? <button className="secondary-button" type="button" onClick={auth.login}>Log In</button> : null}
        {auth?.enabled && auth.authenticated ? <button className="secondary-button" type="button" onClick={auth.logout}>Log Out</button> : null}
        <span className="status">{auth?.label || "Auth optional"}</span>
        <span className="status">{status}</span>
      </div>
    </header>
  );
});
