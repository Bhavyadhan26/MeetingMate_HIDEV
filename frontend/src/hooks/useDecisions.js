import { useMemo } from "react";

export function useDecisions(decisions, filters) {
  return useMemo(() => {
    const query = filters.query.trim().toLowerCase();
    const filtered = decisions.filter((decision) => {
      const statusMatch = filters.status === "all" || decision.status === filters.status;
      const queryMatch = !query || `${decision.text} ${decision.source_excerpt} ${decision.meeting_title}`.toLowerCase().includes(query);
      return statusMatch && queryMatch;
    });

    return [...filtered].sort((a, b) => {
      if (filters.sort === "status") return String(a.status).localeCompare(String(b.status));
      if (filters.sort === "drift") return String(a.drift?.label || "New").localeCompare(String(b.drift?.label || "New"));
      return new Date(b.created_at || 0) - new Date(a.created_at || 0);
    });
  }, [decisions, filters.query, filters.sort, filters.status]);
}
