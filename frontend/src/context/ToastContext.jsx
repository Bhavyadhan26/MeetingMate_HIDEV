import { createContext, useCallback, useContext, useRef, useState } from "react";

const ToastContext = createContext(null);
const MAX_VISIBLE = 5;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const counterRef = useRef(0);
  const timersRef = useRef(new Map());

  const removeToast = useCallback((id) => {
    setToasts((items) => items.map((toast) => toast.id === id ? { ...toast, exiting: true } : toast));
    const existingTimer = timersRef.current.get(id);
    if (existingTimer) clearTimeout(existingTimer);
    const timer = setTimeout(() => {
      setToasts((items) => {
        const dismissed = items.find((toast) => toast.id === id);
        if (dismissed?.onDismiss) dismissed.onDismiss();
        return items.filter((toast) => toast.id !== id);
      });
      timersRef.current.delete(id);
    }, 200);
    timersRef.current.set(id, timer);
  }, []);

  const addToast = useCallback((type, title, message, options = {}) => {
    const id = `toast-${Date.now()}-${++counterRef.current}`;
    const { action = null, duration = 6000, onDismiss = null, persistent = false } = options;
    const actuallyPersistent = persistent || type === "error" || type === "conflict";
    const toast = {
      action,
      id,
      message,
      onDismiss,
      persistent: actuallyPersistent,
      timestamp: new Date().toISOString(),
      title,
      type,
      exiting: false
    };

    setToasts((items) => {
      const updated = [...items, toast];
      return updated.length > MAX_VISIBLE ? updated.slice(updated.length - MAX_VISIBLE) : updated;
    });

    if (!actuallyPersistent) {
      const timer = setTimeout(() => removeToast(id), duration);
      timersRef.current.set(id, timer);
    }
    return id;
  }, [removeToast]);

  return (
    <ToastContext.Provider value={{ addToast, removeToast, toasts }}>
      {children}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return context;
}
