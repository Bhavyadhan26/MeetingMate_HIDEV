import { useCallback, useEffect, useState } from "react";
import { listConflicts } from "../api/client.js";

export function useConflicts(teamId, intervalMs = 15000) {
  const [conflicts, setConflicts] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listConflicts(teamId);
      setConflicts(result.conflicts || []);
      return result.conflicts || [];
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    refresh().catch(() => {});
    const timer = setInterval(() => refresh().catch(() => {}), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs, refresh]);

  return { conflicts, error, loading, refresh, setConflicts };
}
