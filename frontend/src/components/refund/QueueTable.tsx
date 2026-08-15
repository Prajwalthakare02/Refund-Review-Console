import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fetchOrders, formatMinor, rowsOf, type OrderRow } from "@/lib/refund-api";
import { FlagPills } from "./FlagPills";

const PER_PAGE = 25;

const TABS: Array<{ id: "finance" | "support"; label: string }> = [
  { id: "finance", label: "Finance Outflow Queue" },
  { id: "support", label: "Support History View" },
];

export function QueueTable({ onSelect }: { onSelect: (orderId: string) => void }) {
  const [view, setView] = useState<"finance" | "support">("finance");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: ["orders", view, search, page, PER_PAGE],
    queryFn: () => fetchOrders({ view, search, page, per_page: PER_PAGE }),
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
                className="cursor-pointer border-b border-border/60 transition-colors hover:bg-accent"
              >
                <td className="px-3 py-2 font-mono text-xs text-foreground">{r.order_id}</td>
                <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                  {r.customer_id}
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums text-foreground">
                  {money(r.total_paid_formatted, r.total_paid_minor, r.currency)}
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums text-foreground">
                  {money(
                    r.refunded_succeeded_formatted,
                    r.refunded_succeeded_minor,
                    r.currency,
                  )}
                </td>
                <td className="px-3 py-2 text-right font-mono tabular-nums font-semibold text-foreground">
                  {money(r.pending_payout_formatted, r.pending_payout_minor, r.currency)}
                </td>
                <td className="px-3 py-2 text-xs text-muted-foreground">{r.status ?? "—"}</td>
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
