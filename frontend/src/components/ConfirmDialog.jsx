export function ConfirmDialog({ confirmLabel = "Confirm", message, onCancel, onConfirm, title }) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <h3 id="confirm-title">{title}</h3>
        <p>{message}</p>
        <div className="inline-actions">
          <button className="danger-button" type="button" onClick={onConfirm}>{confirmLabel}</button>
          <button className="secondary-button" type="button" onClick={onCancel}>Cancel</button>
        </div>
      </section>
    </div>
  );
}
