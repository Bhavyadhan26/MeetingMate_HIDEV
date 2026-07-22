import { useEffect, useMemo, useState } from "react";
import { getTranscriptJob } from "../api/client.js";

const steps = ["Transcribing", "Redacting", "Extracting", "Detecting Drift", "Persisting"];

export function useTranscriptJob(jobId) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [pollCount, setPollCount] = useState(0);

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      setError(null);
      setPollCount(0);
      return undefined;
    }
    let cancelled = false;
    const timer = setInterval(async () => {
      try {
        const result = await getTranscriptJob(jobId);
        if (cancelled) return;
        setJob(result);
        setPollCount((count) => count + 1);
        if (result.status === "completed" || result.status === "failed") {
          clearInterval(timer);
        }
      } catch (err) {
        if (cancelled) return;
        setError(err);
        clearInterval(timer);
      }
    }, 500);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [jobId]);

  const progress = useMemo(() => {
    if (!jobId) return 0;
    if (job?.status === "completed") return 100;
    if (job?.status === "failed") return 100;
    return Math.min(90, 12 + pollCount * 12);
  }, [job?.status, jobId, pollCount]);

  const activeStep = useMemo(() => {
    if (!jobId) return -1;
    if (job?.status === "completed") return steps.length;
    if (job?.status === "failed") return Math.max(0, Math.min(steps.length - 1, Math.floor(progress / 22)));
    return Math.max(0, Math.min(steps.length - 1, Math.floor(progress / 22)));
  }, [job?.status, jobId, progress]);

  return { activeStep, error, job, progress, steps };
}
