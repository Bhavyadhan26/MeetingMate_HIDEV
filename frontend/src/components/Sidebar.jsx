import React from "react";
import { NavLink } from "react-router-dom";

const links = [
  ["/", "dashboard", "Dashboard"],
  ["/memory", "account_balance", "Memory Ledger"],
  ["/meetings", "groups", "Team Meetings"],
  ["/decisions", "gavel", "Audit Logs"],
  ["/conflicts", "warning", "Conflicts"],
  ["/design-system", "deployed_code", "Design System"]
];

export const Sidebar = React.memo(function Sidebar({ conflictCount }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div>
          <h1>AuditIQ</h1>
          <p>Precision Intelligence</p>
        </div>
      </div>
      <nav className="nav-list" aria-label="Primary">
        {links.map(([to, icon, label]) => (
          <NavLink className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`} end={to === "/"} key={to} to={to}>
            <span className="material-symbols-outlined">{icon}</span>
            <span>{label}</span>
            {label === "Conflicts" ? <span className="nav-badge">{conflictCount}</span> : null}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-actions">
        <NavLink className="new-audit-button" to="/upload">
          <span className="material-symbols-outlined">add</span>
          <span>New Audit</span>
        </NavLink>
      </div>
      <div className="sidebar-footer">
        <NavLink className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`} to="/settings">
          <span className="material-symbols-outlined">settings</span>
          <span>Settings</span>
        </NavLink>
        <a className="nav-link" href="#support">
          <span className="material-symbols-outlined">help_outline</span>
          <span>Support</span>
        </a>
        <div className="auditor-profile">
          <div className="auditor-avatar">SA</div>
          <div>
            <strong>Senior Auditor</strong>
            <small>ID: 8829-QX</small>
          </div>
        </div>
      </div>
    </aside>
  );
});
