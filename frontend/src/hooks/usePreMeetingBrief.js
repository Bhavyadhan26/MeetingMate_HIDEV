import { useCallback, useState } from "react";
import { createPreMeetingBrief } from "../api/client.js";

export function usePreMeetingBrief(teamId) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const generate = useCallback(async (agenda) => {
    setLoading(true);
    setError(null);
    try {
      const result = await createPreMeetingBrief({ team_id: teamId, agenda });
      setData(result);
      return result;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  return { data, error, generate, loading };
}
