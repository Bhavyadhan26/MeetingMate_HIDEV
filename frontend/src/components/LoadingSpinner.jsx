export function LoadingSpinner({ label = "Loading" }) {
  return (
    <div className="loading-state">
      <span className="spinner" aria-hidden="true"></span>
      <span>{label}</span>
    </div>
  );
}
