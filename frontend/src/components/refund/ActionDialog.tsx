import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { postDecision } from "@/lib/refund-api";

export function ActionDialog({
  refundId,
  onClose,
}: {
  refundId: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [action, setAction] = useState<"approve" | "reject">("approve");
  const [reason, setReason] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      postDecision(refundId, {
        action,
        reason: reason.trim(),
        idempotency_key: crypto.randomUUID(),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["orders"] });
      void qc.invalidateQueries({ queryKey: ["metrics"] });
      void qc.invalidateQueries({ queryKey: ["order-detail"] });
      onClose();
    },
  });

  const disabled = mutation.isPending || reason.trim().length === 0;

  return (
    <div className="fixed inset-0 z-60 flex items-center justify-center bg-background/70 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-xl">
        <h3 className="text-base font-semibold text-foreground">Action Decision</h3>
        <p className="mt-1 font-mono text-xs text-muted-foreground">refund {refundId}</p>

        <div className="mt-4 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setAction("approve")}
            className={
              "rounded-lg border px-3 py-2 text-sm font-medium transition-colors " +
              (action === "approve"
                ? "border-success bg-success/15 text-success"
                : "border-border text-muted-foreground hover:bg-accent")
            }
          >
            Approve
          </button>
          <button
            type="button"
            onClick={() => setAction("reject")}
            className={
              "rounded-lg border px-3 py-2 text-sm font-medium transition-colors " +
              (action === "reject"
                ? "border-destructive bg-destructive/15 text-destructive"
                : "border-border text-muted-foreground hover:bg-accent")
            }
          >
            Reject
          </button>
        </div>

        <label className="mt-4 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Reason (required)
        </label>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={4}
          className="mt-2 w-full resize-none rounded-lg border border-input bg-background p-3 text-sm text-foreground outline-none focus:border-ring"
          placeholder="Explain the decision for the audit trail…"
        />

        {mutation.isError && (
          <p className="mt-2 text-xs text-destructive">
            {(mutation.error as Error).message}
          </p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={mutation.isPending}
            className="rounded-lg border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-accent disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={() => mutation.mutate()}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {mutation.isPending && (
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
            )}
            {mutation.isPending ? "Submitting…" : `Submit ${action}`}
          </button>
        </div>
      </div>
    </div>
  );
}
