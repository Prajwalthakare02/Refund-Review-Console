import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchOrderDetail,
  formatMinor,
  type OrderDetailData,
  type TimelineEvent,
} from "@/lib/refund-api";
import { FlagPills } from "./FlagPills";
import { ActionDialog } from "./ActionDialog";

const TONES: Record<string, string> = {
  "refund.requested": "border-warning/40 bg-warning/10 text-warning",
  "refund.succeeded": "border-success/40 bg-success/10 text-success",
  "refund.failed": "border-destructive/40 bg-destructive/10 text-destructive",
  "chargeback.opened": "border-chargeback/40 bg-chargeback/10 text-chargeback",
};

const DOTS: Record<string, string> = {
  "refund.requested": "bg-warning",
  "refund.succeeded": "bg-success",
  "refund.failed": "bg-destructive",
  "chargeback.opened": "bg-chargeback",
};

function TimelineRow({
  ev,
  currency,
  canAct,
  onDecide,
}: {
  ev: TimelineEvent;
  currency?: string | undefined;
  canAct: boolean;
  onDecide: (refundId: string) => void;
}) {
  const needsDecision = ev.type === "refund.requested" && !!ev.refund_id;

  return (
    <li className="relative pl-8">
      <span
        className={`absolute left-[9px] top-2 h-2.5 w-2.5 rounded-full ring-4 ring-card ${
          DOTS[ev.type] ?? "bg-muted-foreground"
        }`}
      />
      <div className="rounded-lg border border-border bg-background p-3">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${
              TONES[ev.type] ?? "border-border bg-muted text-muted-foreground"
            }`}
          >
            {ev.type}
          </span>
          {ev.status && (
            <span className="text-[11px] font-medium text-muted-foreground">{ev.status}</span>
          )}
          <span className="ml-auto font-mono text-[11px] text-muted-foreground">
            {ev.occurred_at_utc}
          </span>
        </div>
        <div className="mt-2 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">
          <div>
            Amount:{" "}
            <span className="font-mono text-foreground">
              {ev.amount_formatted ?? formatMinor(ev.amount_minor, currency)}
            </span>{" "}
            <span className="font-mono">({ev.amount_minor ?? "—"} minor)</span>
          </div>
          <div>
            Refund ID: <span className="font-mono text-foreground">{ev.refund_id ?? "—"}</span>
          </div>
          <div>
            Source: <span className="text-foreground">{ev.source ?? "—"}</span>
          </div>
          <div>
            Reason: <span className="text-foreground">{ev.reason ?? "—"}</span>
          </div>
        </div>
        {needsDecision && canAct && (
          <button
            type="button"
            onClick={() => onDecide(ev.refund_id as string)}
            className="mt-3 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:opacity-90"
          >
            Action Decision
          </button>
        )}
      </div>
    </li>
  );
}

function Stat({ label, value, subtle }: { label: string; value: string; subtle?: string }) {
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 font-mono text-sm font-semibold text-foreground">{value}</div>
      {subtle && <div className="mt-1 text-xs text-muted-foreground">{subtle}</div>}
    </div>
  );
}

export function OrderDetail({ orderId, onClose }: { orderId: string; onClose: () => void }) {
  const [refundId, setRefundId] = useState<string | null>(null);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["order-detail", orderId],
    queryFn: () => fetchOrderDetail(orderId),
  });
  const pendingRefundIds = new Set(
    (data?.refunds ?? [])
      .filter((refund) => refund.status === "pending")
      .map((refund) => refund.refund_id),
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-background/70 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="my-8 w-full max-w-3xl rounded-xl border border-border bg-card shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-4 border-b border-border p-5">
          <div>
            <h2 className="font-mono text-lg font-semibold text-foreground">{orderId}</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Customer <span className="font-mono text-foreground">{data?.customer_id ?? "—"}</span>
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Placed at{" "}
              <span className="font-mono text-foreground">{data?.order?.placed_at ?? "—"}</span>
            </p>
            <div className="mt-2">
              <FlagPills flags={data?.flags} />
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-border px-2.5 py-1 text-sm text-muted-foreground hover:bg-accent"
          >
            Close
          </button>
        </header>

        <div className="space-y-4 p-5">
          {data?.order && (
            <section className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                <span className="font-semibold uppercase tracking-wider">Derived state</span>
                <span className="font-mono">
                  {data.timeline?.length ?? 0} events · {data.refunds?.length ?? 0} refund chains
                </span>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Stat
                  label="Total paid"
                  value={data.order.total_paid_formatted}
                  subtle={`${data.order.total_paid_minor.toLocaleString()} minor units`}
                />
                <Stat
                  label="Refunded succeeded"
                  value={formatMinor(data.refunded_succeeded_minor, data.order.currency)}
                  subtle={`${(data.refunded_succeeded_minor ?? 0).toLocaleString()} minor units`}
                />
                <Stat
                  label="Pending payout"
                  value={formatMinor(data.pending_payout_minor, data.order.currency)}
                  subtle={`${(data.pending_payout_minor ?? 0).toLocaleString()} minor units`}
                />
                <Stat
                  label="Remaining refundable"
                  value={formatMinor(data.remaining_refundable_minor, data.order.currency)}
                  subtle={`${(data.remaining_refundable_minor ?? 0).toLocaleString()} minor units`}
                />
              </div>
              <div className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                Derived from ordered event chains for{" "}
                <span className="font-mono text-foreground">{data.order.order_id}</span>. Refund
                states are resolved from `occurred_at_utc`, not arrival order.
              </div>
            </section>
          )}

          {!!data?.warnings?.length && (
            <div className="space-y-2">
              {data.warnings.map((w, i) => (
                <div
                  key={i}
                  className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm font-medium text-destructive"
                >
                  ⚠️ {w}
                </div>
              ))}
            </div>
          )}

          {isLoading && <p className="text-sm text-muted-foreground">Loading timeline…</p>}
          {isError && <p className="text-sm text-destructive">Failed to load order.</p>}

          {!!data?.timeline?.length && (
            <ol className="relative space-y-3 before:absolute before:left-3.5 before:top-2 before:h-[calc(100%-1rem)] before:w-px before:bg-border">
              {data.timeline.map((ev, i) => (
                <TimelineRow
                  key={i}
                  ev={ev}
                  currency={data.currency}
                  canAct={!ev.refund_id || pendingRefundIds.has(ev.refund_id)}
                  onDecide={setRefundId}
                />
              ))}
            </ol>
          )}
          {data && !data.timeline?.length && !isLoading && (
            <p className="text-sm text-muted-foreground">No timeline events.</p>
          )}
        </div>
      </div>

      {refundId && (
        <div onClick={(e) => e.stopPropagation()}>
          <ActionDialog refundId={refundId} onClose={() => setRefundId(null)} />
        </div>
      )}
    </div>
  );
}
