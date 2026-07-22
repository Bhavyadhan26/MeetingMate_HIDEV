import { useCallback, useEffect, useState } from "react";
import { searchMemory } from "../api/client.js";

export function useMemorySearch(teamId) {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(timer);
  }, [query]);

  const runSearch = useCallback(async (nextQuery = debouncedQuery) => {
    if (!nextQuery.trim()) return null;
    setLoading(true);
    setError(null);
    try {
      const result = await searchMemory(nextQuery, teamId);
      setData(result);
      return result;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [debouncedQuery, teamId]);

  return { data, debouncedQuery, error, loading, query, runSearch, setQuery };
}
