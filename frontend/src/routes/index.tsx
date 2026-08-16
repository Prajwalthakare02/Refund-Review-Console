import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { MetricBar } from "@/components/refund/MetricBar";
import { QueueTable } from "@/components/refund/QueueTable";
import { OrderDetail } from "@/components/refund/OrderDetail";
import { fetchMetrics } from "@/lib/refund-api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Refund Review Console — Finance Operations" },
      {
        name: "description",
        content:
          "Internal console to review refund queues, pending payouts, risk flags and approve or reject refund decisions.",
      },
      { property: "og:title", content: "Refund Review Console — Finance Operations" },
      {
        property: "og:description",
        content:
          "Review refund queues, pending payouts and risk flags, then approve or reject refunds.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  const [orderId, setOrderId] = useState<string | null>(null);
  const { data: metrics } = useQuery({
    queryKey: ["metrics-summary"],
    queryFn: fetchMetrics,
    refetchOnWindowFocus: false,
  });

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-card/60">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-foreground">
              Refund Review Console
            </h1>
            <p className="text-xs text-muted-foreground">
              Finance operations · outflow approvals &amp; refund audit
            </p>
          </div>
          <div className="text-right">
            <div className="rounded-full border border-border px-3 py-1 font-mono text-[11px] text-muted-foreground">
              api :8000
            </div>
            <div className="mt-1 font-mono text-[10px] text-muted-foreground">
              pinned {metrics?.pinned_now_ist ?? "—"} IST
            </div>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl space-y-5 px-6 py-6">
        <MetricBar />
        <QueueTable onSelect={setOrderId} />
      </div>

      {orderId && <OrderDetail orderId={orderId} onClose={() => setOrderId(null)} />}
    </main>
  );
}
