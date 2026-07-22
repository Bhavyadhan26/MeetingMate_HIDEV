import { Toast } from "./Toast.jsx";
import { useToast } from "../context/ToastContext.jsx";

export function ToastContainer() {
  const { removeToast, toasts } = useToast();
  return (
    <div className="toast-container" aria-live="polite">
      {toasts.slice(-5).map((toast) => <Toast key={toast.id} toast={toast} onDismiss={removeToast} />)}
    </div>
  );
}
