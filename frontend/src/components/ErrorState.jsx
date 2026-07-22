export function ErrorState({ error, onRetry }) {
  const detail = error?.detail || error || {};
  return (
    <div className="error-state">
      <strong>{detail.code || "Request failed"}</strong>
      <p>{detail.message || "Something went wrong while loading this section."}</p>
      {onRetry ? <button type="button" onClick={onRetry}>Retry</button> : null}
    </div>
  );
}
