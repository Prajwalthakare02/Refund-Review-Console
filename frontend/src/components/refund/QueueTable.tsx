import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fetchOrders, formatMinor, rowsOf, type OrderRow } from "@/lib/refund-api";
import { FlagPills } from "./FlagPills";

const PER_PAGE = 25;

const TABS: Array<{ id: "finance" | "support"; label: string }> = [
  { id: "finance", label: "Finance Outflow Queue" },
  { id: "support", label: "Support History View" },
];

const STATUS_FILTERS: Array<{ id: "all" | "pending" | "approved" | "rejected"; label: string }> = [
  { id: "all", label: "All" },
  { id: "pending", label: "Pending" },
  { id: "approved", label: "Approved" },
  { id: "rejected", label: "Rejected" },
];

function normalizeStatus(status?: string): "pending" | "approved" | "rejected" | "other" {
  if (status === "pending_approval" || status === "pending") return "pending";
  if (status === "approved") return "approved";
  if (status === "rejected") return "rejected";
  return "other";
}

export function QueueTable({ onSelect }: { onSelect: (orderId: string) => void }) {
  const [view, setView] = useState<"finance" | "support">("finance");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<"all" | "pending" | "approved" | "rejected">(
    "pending",
  );

  const effectiveStatusFilter = view === "finance" ? "pending" : statusFilter;

  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: ["orders", view, search, effectiveStatusFilter, page, PER_PAGE],
    queryFn: () =>
      fetchOrders({ view, search, status: effectiveStatusFilter, page, per_page: PER_PAGE }),
    placeholderData: keepPreviousData,
  });

  const rows = rowsOf(data);
  const total = data?.total;

  const money = (fmt: string | undefined, minor: number | undefined, cur?: string) =>
    fmt ?? formatMinor(minor, cur);

  return (
    <section className="rounded-xl border border-border bg-card shadow-sm">
      <div className="flex flex-wrap items-center gap-3 border-b border-border p-3">
        <div className="flex rounded-lg bg-muted p-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => {
                setView(t.id);
                setPage(1);
                setStatusFilter(t.id === "finance" ? "pending" : "all");
              }}
              className={
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors " +
                (view === t.id
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground")
              }
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {STATUS_FILTERS.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => {
                if (view === "finance" && s.id !== "pending") return;
                setStatusFilter(s.id);
                setPage(1);
              }}
              disabled={view === "finance" && s.id !== "pending"}
              className={
                "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors " +
                (effectiveStatusFilter === s.id
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border text-muted-foreground hover:bg-accent") +
                (view === "finance" && s.id !== "pending" ? " cursor-not-allowed opacity-40" : "")
              }
            >
              {s.label}
            </button>
          ))}
        </div>

        <input
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="Search order_id or customer_id…"
          className="ml-auto w-full max-w-xs rounded-lg border border-input bg-background px-3 py-1.5 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-ring"
        />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <th className="px-3 py-2 font-semibold">Order ID</th>
              <th className="px-3 py-2 font-semibold">Customer ID</th>
              <th className="px-3 py-2 text-right font-semibold">Total Paid</th>
              <th className="px-3 py-2 text-right font-semibold">Refunded Succeeded</th>
              <th className="px-3 py-2 text-right font-semibold">Pending Payout</th>
              <th className="px-3 py-2 font-semibold">Status</th>
              <th className="px-3 py-2 font-semibold">Flags</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r: OrderRow) => (
              <tr
                key={r.order_id}
                onClick={() => onSelect(r.order_id)}
                className={
                  "cursor-pointer border-b border-border/60 transition-colors hover:bg-accent " +
                  (normalizeStatus(r.status) === "approved"
                    ? "bg-success/5"
                    : normalizeStatus(r.status) === "rejected"
                      ? "bg-destructive/5"
                      : "")
                }
              >
                <td className="px-3 py-2 font-mono text-xs text-foreground">{r.order_id}</td>
                <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                  {r.customer_id}
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums text-foreground">
                  {money(r.total_paid_formatted, r.total_paid_minor, r.currency)}
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums text-foreground">
                  {money(r.refunded_succeeded_formatted, r.refunded_succeeded_minor, r.currency)}
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums font-semibold text-foreground">
                  {money(r.pending_payout_formatted, r.pending_payout_minor, r.currency)}
                </td>
                <td className="px-3 py-2 text-xs">
                  <span
                    className={
                      "rounded-full border px-2 py-0.5 font-medium " +
                      (normalizeStatus(r.status) === "approved"
                        ? "border-success/40 bg-success/10 text-success"
                        : normalizeStatus(r.status) === "rejected"
                          ? "border-destructive/40 bg-destructive/10 text-destructive"
                          : normalizeStatus(r.status) === "pending"
                            ? "border-warning/40 bg-warning/10 text-warning"
                            : "border-border bg-muted text-muted-foreground")
                    }
                  >
                    {r.status ?? "—"}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <FlagPills flags={r.flags} />
                </td>
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td colSpan={7} className="px-3 py-10 text-center text-sm text-muted-foreground">
                  {isLoading
                    ? "Loading orders…"
                    : isError
                      ? "Could not reach /api/orders."
                      : "No orders match this view."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-border p-3 text-xs text-muted-foreground">
        <span>
          Page {page}
          {total !== undefined ? ` · ${total} results` : ""}
          {isFetching ? " · refreshing…" : ""}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="rounded-md border border-border px-2.5 py-1 hover:bg-accent disabled:opacity-40"
          >
            Prev
          </button>
          <button
            type="button"
            disabled={rows.length < PER_PAGE}
            onClick={() => setPage((p) => p + 1)}
            className="rounded-md border border-border px-2.5 py-1 hover:bg-accent disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </section>
  );
}
