import React from "react";
import { NavLink } from "react-router-dom";

const links = [
  ["/", "Dashboard"],
  ["/upload", "Upload"],
  ["/meetings", "Meetings"],
  ["/decisions", "Decisions"],
  ["/memory", "Memory"],
  ["/conflicts", "Conflicts"],
  ["/settings", "Settings"]
];

export const Sidebar = React.memo(function Sidebar({ conflictCount }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">M</span>
        <div>
          <h1>MeetingMate</h1>
          <p>AI Meeting Intelligence</p>
        </div>
      </div>
      <nav className="nav-list" aria-label="Primary">
        {links.map(([to, label]) => (
          <NavLink className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`} end={to === "/"} key={to} to={to}>
            <span>{label}</span>
            {label === "Conflicts" ? <span className="nav-badge">{conflictCount}</span> : null}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
});
