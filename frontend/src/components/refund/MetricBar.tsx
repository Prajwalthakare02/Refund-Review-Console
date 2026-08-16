import { useQuery } from "@tanstack/react-query";
import {
  fetchMetrics,
  formatMinor,
  type MetricCurrency,
  type MetricsSummary,
} from "@/lib/refund-api";

const SYMBOLS: Record<string, string> = { INR: "₹", USD: "$" };

function Card({ code, data }: { code: string; data?: MetricCurrency | undefined }) {
  const display = data ?? { amount_minor: 0, amount_formatted: formatMinor(0, code), count: 0 };

  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Pending payout · {code}
        </span>
        <span className="rounded-md bg-accent px-2 py-0.5 font-mono text-xs text-accent-foreground">
          {SYMBOLS[code] ?? ""}
        </span>
      </div>
      <div className="mt-3 font-mono text-3xl font-semibold tabular-nums text-foreground">
        {display.amount_formatted}
      </div>
      <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
        <span className="font-mono tabular-nums">
          {display.amount_minor.toLocaleString()}{" "}
          {code === "INR" ? "paise" : code === "USD" ? "cents" : "minor"}
        </span>
        <span className="h-3 w-px bg-border" />
        <span>
          <span className="font-semibold text-foreground">{display.count}</span> pending
        </span>
      </div>
    </div>
  );
}

export function MetricBar() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["metrics-summary"],
    queryFn: fetchMetrics,
  });

  const metrics = data as MetricsSummary | undefined;

  const pick = (code: string): MetricCurrency | undefined => {
    const raw = metrics as Record<string, unknown> | undefined;
    if (!raw) return undefined;
    const direct = (raw[code] ?? raw[code.toLowerCase()]) as MetricCurrency | undefined;
    if (direct) return direct;
    const pendingPayout = raw["pending_payout"] as Record<string, MetricCurrency> | undefined;
    if (pendingPayout?.[code]) return pendingPayout[code];
    const nested = (raw["currencies"] ?? raw["totals"] ?? raw["summary"]) as
      Record<string, MetricCurrency> | MetricCurrency[] | undefined;
    if (Array.isArray(nested)) return nested.find((n) => n.currency === code);
    return nested?.[code];
  };

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border bg-card px-4 py-3 text-xs text-muted-foreground shadow-sm">
        <span className="font-semibold uppercase tracking-wider">Pinned now</span>
        <span className="font-mono">
          {metrics?.pinned_now_ist ?? "—"} ({metrics?.pinned_now ?? "—"})
        </span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Card code="INR" data={pick("INR")} />
        <Card code="USD" data={pick("USD")} />
        {isLoading && (
          <p className="col-span-full text-xs text-muted-foreground">Loading metrics…</p>
        )}
        {isError && (
          <p className="col-span-full text-xs text-destructive">
            Could not reach {`/api/metrics/summary`}.
          </p>
        )}
      </div>
    </section>
  );
}
