import React, { Suspense, lazy, useCallback, useEffect, useMemo, useState } from "react";
import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout.jsx";
import { LoadingSpinner } from "./components/LoadingSpinner.jsx";
import { ToastContainer } from "./components/ToastContainer.jsx";
import { TeamProvider } from "./context/TeamContext.jsx";
import { ToastProvider } from "./context/ToastContext.jsx";
import { setAccessTokenProvider } from "./api/client.js";

const DashboardPage = lazy(() => import("./pages/DashboardPage.jsx"));
const UploadPage = lazy(() => import("./pages/UploadPage.jsx"));
const MeetingsPage = lazy(() => import("./pages/MeetingsPage.jsx"));
const DecisionsPage = lazy(() => import("./pages/DecisionsPage.jsx"));
const MemoryPage = lazy(() => import("./pages/MemoryPage.jsx"));
const ConflictsPage = lazy(() => import("./pages/ConflictsPage.jsx"));
const SettingsPage = lazy(() => import("./pages/SettingsPage.jsx"));
const DesignSystemPage = lazy(() => import("./pages/DesignSystemPage.jsx"));

function loadJson(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) || fallback;
  } catch {
    return fallback;
  }
}

function saveJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function AppContent() {
  const [actions, setActions] = useState([]);
  const [activities, setActivities] = useState(() => loadJson("meetingmate.react.activities", []));
  const [auth, setAuth] = useState({ enabled: false, authenticated: false, label: "Auth optional" });
  const [conflicts, setConflicts] = useState([]);
  const [decisions, setDecisions] = useState(() => loadJson("meetingmate.react.decisions", []));
  const [meetings, setMeetings] = useState(() => loadJson("meetingmate.react.meetings", []));
  const [status, setStatus] = useState("Ready");

  const addActivity = useCallback((type, text, detail = "") => {
    setActivities((items) => {
      const next = [{ id: `${Date.now()}-${Math.random().toString(16).slice(2)}`, type, text, detail, at: new Date().toISOString() }, ...items].slice(0, 20);
      saveJson("meetingmate.react.activities", next);
      return next;
    });
  }, []);

  const addMeetingResult = useCallback((result, payload) => {
    const meeting = {
      id: result.meeting?.id || result.trace_id,
      title: result.meeting?.title || payload.title || "Untitled meeting",
      team_id: result.meeting?.team_id || payload.team_id || "demo-team",
      trace_id: result.trace_id,
      status: "completed",
      created_at: new Date().toISOString()
    };
    setMeetings((items) => {
      const next = [meeting, ...items.filter((item) => item.id !== meeting.id)].slice(0, 50);
      saveJson("meetingmate.react.meetings", next);
      return next;
    });
    const normalized = (result.decisions || []).map((decision) => ({
      ...decision,
      meeting_title: meeting.title,
      created_at: decision.created_at || meeting.created_at
    }));
    setDecisions((items) => {
      const byId = new Map(items.map((item) => [item.id, item]));
      normalized.forEach((decision) => byId.set(decision.id, decision));
      const next = Array.from(byId.values());
      saveJson("meetingmate.react.decisions", next);
      return next;
    });
    setActions(result.action_items || []);
    addActivity("processed", meeting.title, `Trace ${result.trace_id}`);
    return meeting;
  }, [addActivity]);

  const replaceDecision = useCallback((decision) => {
    setDecisions((items) => {
      const next = items.map((item) => item.id === decision.id ? { ...item, ...decision } : item);
      saveJson("meetingmate.react.decisions", next);
      return next;
    });
  }, []);

  useEffect(() => {
    async function initAuth() {
      try {
        const response = await fetch(`${window.MEETINGMATE_API_BASE || "http://localhost:8000"}/v1/auth/config`);
        const config = response.ok ? await response.json() : {};
        const domain = config.domain || window.MEETINGMATE_AUTH0_DOMAIN;
        const clientId = config.client_id || window.MEETINGMATE_AUTH0_CLIENT_ID;
        const audience = config.audience || window.MEETINGMATE_AUTH0_AUDIENCE;
        if (!domain || !clientId || !window.auth0) {
          setAuth({ enabled: false, authenticated: false, label: "Auth optional" });
          return;
        }
        const auth0Client = await window.auth0.createAuth0Client({
          domain,
          clientId,
          authorizationParams: { audience, redirect_uri: window.location.origin }
        });
        if (window.location.search.includes("code=") && window.location.search.includes("state=")) {
          await auth0Client.handleRedirectCallback();
          window.history.replaceState({}, document.title, window.location.pathname);
        }
        const authenticated = await auth0Client.isAuthenticated();
        if (authenticated) {
          const user = await auth0Client.getUser();
          setAccessTokenProvider(() => auth0Client.getTokenSilently());
          setAuth({
            enabled: true,
            authenticated: true,
            label: user.email || user.name || "Signed in",
            login: () => auth0Client.loginWithRedirect(),
            logout: () => auth0Client.logout({ logoutParams: { returnTo: window.location.origin } })
          });
        } else {
          setAuth({
            enabled: true,
            authenticated: false,
            label: config.required ? "Sign in required" : "Signed out",
            login: () => auth0Client.loginWithRedirect(),
            logout: () => auth0Client.logout({ logoutParams: { returnTo: window.location.origin } })
          });
        }
      } catch {
        setAuth({ enabled: false, authenticated: false, label: "Auth optional" });
      }
    }
    initAuth();
  }, []);

  const appState = useMemo(() => ({
    actions,
    activities,
    addActivity,
    addMeetingResult,
    conflicts,
    decisions,
    meetings,
    replaceDecision,
    setActions,
    setConflicts,
    setDecisions,
    setMeetings,
    setStatus
  }), [actions, activities, addActivity, addMeetingResult, conflicts, decisions, meetings, replaceDecision]);

  return (
    <TeamProvider>
      <Routes>
        <Route element={<Layout auth={auth} conflictCount={conflicts.length} status={status} />}>
          <Route path="/" element={<Suspense fallback={<LoadingSpinner label="Loading dashboard" />}><DashboardPage appState={appState} /></Suspense>} />
          <Route path="/upload" element={<Suspense fallback={<LoadingSpinner label="Loading upload" />}><UploadPage appState={appState} /></Suspense>} />
          <Route path="/meetings" element={<Suspense fallback={<LoadingSpinner label="Loading meetings" />}><MeetingsPage appState={appState} /></Suspense>} />
          <Route path="/decisions" element={<Suspense fallback={<LoadingSpinner label="Loading decisions" />}><DecisionsPage appState={appState} /></Suspense>} />
          <Route path="/memory" element={<Suspense fallback={<LoadingSpinner label="Loading memory" />}><MemoryPage appState={appState} /></Suspense>} />
          <Route path="/conflicts" element={<Suspense fallback={<LoadingSpinner label="Loading conflicts" />}><ConflictsPage appState={appState} /></Suspense>} />
          <Route path="/settings" element={<Suspense fallback={<LoadingSpinner label="Loading settings" />}><SettingsPage appState={appState} /></Suspense>} />
          <Route path="/design-system" element={<Suspense fallback={<LoadingSpinner label="Loading design system" />}><DesignSystemPage appState={appState} /></Suspense>} />
        </Route>
      </Routes>
    </TeamProvider>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <AppContent />
      <ToastContainer />
    </ToastProvider>
  );
}
