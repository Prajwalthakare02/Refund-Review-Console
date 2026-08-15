import type { OrderFlags } from "@/lib/refund-api";

const PILLS: Array<{ key: keyof OrderFlags; label: string; tone: "warn" | "danger" }> = [
  { key: "is_high_value", label: "⚠️ High Value", tone: "warn" },
  { key: "is_over_refunded", label: "⚠️ Over-refunded", tone: "warn" },
  { key: "has_chargeback", label: "🚨 Double Loss Risk", tone: "danger" },
  { key: "has_currency_mismatch", label: "⚠️ Currency Mismatch", tone: "warn" },
  { key: "is_orphan_order", label: "⚠️ Missing Order", tone: "warn" },
];

export function FlagPills({ flags }: { flags?: OrderFlags | undefined }) {
  if (!flags) return null;
  const active = PILLS.filter((p) => flags[p.key]);
  if (!active.length) return <span className="text-xs text-muted-foreground">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {active.map((p) => (
        <span
          key={p.key}
          className={
            "whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium " +
            (p.tone === "danger"
              ? "border-destructive/40 bg-destructive/10 text-destructive"
              : "border-warning/40 bg-warning/10 text-warning")
          }
        >
          {p.label}
        </span>
      ))}
    </div>
  );
}
