import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar.jsx";
import { Topbar } from "./Topbar.jsx";

export function Layout({ auth, conflictCount, status }) {
  return (
    <div className="app-shell">
      <Sidebar conflictCount={conflictCount} />
      <main className="main-shell">
        <Topbar auth={auth} status={status} />
        <Outlet />
      </main>
    </div>
  );
}
