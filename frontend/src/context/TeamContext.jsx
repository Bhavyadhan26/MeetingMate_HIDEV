import { createContext, useContext, useMemo, useState } from "react";

const TeamContext = createContext(null);

export function TeamProvider({ children }) {
  const [teamId, setTeamId] = useState(() => localStorage.getItem("meetingmate.teamId") || "demo-team");
  const value = useMemo(() => ({
    teamId,
    setTeamId: (nextTeamId) => {
      setTeamId(nextTeamId);
      localStorage.setItem("meetingmate.teamId", nextTeamId);
    }
  }), [teamId]);

  return <TeamContext.Provider value={value}>{children}</TeamContext.Provider>;
}

export function useTeam() {
  const context = useContext(TeamContext);
  if (!context) {
    throw new Error("useTeam must be used within TeamProvider");
  }
  return context;
}
