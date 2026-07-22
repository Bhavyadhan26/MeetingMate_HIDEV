import { useEffect, useState } from "react";

const icons = {
  conflict: "!",
  error: "x",
  info: "i",
  success: "OK",
  warning: "!"
};

function formatTime(timestamp) {
  return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(new Date(timestamp));
}

export function Toast({ toast, onDismiss }) {
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    if (toast.exiting) setExiting(true);
  }, [toast.exiting]);

  function dismiss() {
    onDismiss(toast.id);
  }

  function runAction(event) {
    event.stopPropagation();
    toast.action?.onClick?.();
    dismiss();
  }

  return (
    <article className={`toast toast-${toast.type} ${exiting ? "toast-exit" : "toast-enter"}`} onClick={dismiss}>
      <span className="toast-icon" aria-hidden="true">{icons[toast.type] || "i"}</span>
      <div className="toast-content">
        <p className="toast-title">{toast.title}</p>
        <p className="toast-message">{toast.message}</p>
        <div className="toast-footer">
          <span className="toast-timestamp">{formatTime(toast.timestamp)}</span>
          {toast.action ? <button className="toast-action" onClick={runAction} type="button">{toast.action.label}</button> : null}
        </div>
      </div>
      <button className="toast-close" onClick={(event) => { event.stopPropagation(); dismiss(); }} type="button" aria-label="Dismiss toast">x</button>
    </article>
  );
}
