export const API_BASE = "http://localhost:8000/api";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export type MetricCurrency = {
  currency?: string;
  amount_formatted: string;
  amount_minor: number;
  count: number;
};

export type MetricsSummary = Record<string, MetricCurrency> & {
  [k: string]: unknown;
};

export type OrderFlags = {
  is_high_value?: boolean;
  is_over_refunded?: boolean;
  has_chargeback?: boolean;
  has_currency_mismatch?: boolean;
  is_orphan_order?: boolean;
};

export type OrderRow = {
  order_id: string;
  customer_id: string;
  total_paid_formatted?: string;
  total_paid_minor?: number;
  refunded_succeeded_formatted?: string;
  refunded_succeeded_minor?: number;
  pending_payout_formatted?: string;
  pending_payout_minor?: number;
  currency?: string;
  status?: string;
  flags?: OrderFlags;
};

export type OrdersResponse = {
  orders?: OrderRow[];
  items?: OrderRow[];
  results?: OrderRow[];
  data?: OrderRow[];
  total?: number;
  page?: number;
  per_page?: number;
};

export type TimelineEvent = {
  type: string;
  status?: string;
  occurred_at_utc: string;
  amount_minor?: number;
  amount_formatted?: string;
  refund_id?: string;
  source?: string;
  reason?: string;
};

export type OrderDetailData = {
  order_id: string;
  customer_id?: string;
  currency?: string;
  warnings?: string[];
  timeline?: TimelineEvent[];
  flags?: OrderFlags;
};

export const fetchMetrics = () => req<MetricsSummary>("/metrics/summary");

export const fetchOrders = (p: {
  view: "finance" | "support";
  search: string;
  page: number;
  per_page: number;
}) => {
  const qs = new URLSearchParams({
    view: p.view,
    search: p.search,
    page: String(p.page),
    per_page: String(p.per_page),
  });
  return req<OrdersResponse>(`/orders?${qs.toString()}`);
};

export const fetchOrderDetail = (orderId: string) =>
  req<OrderDetailData>(`/orders/${encodeURIComponent(orderId)}`);

export const postDecision = (
  refundId: string,
  body: { action: "approve" | "reject"; reason: string; idempotency_key: string },
) =>
  req<unknown>(`/refunds/${encodeURIComponent(refundId)}/decision`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export function rowsOf(res: OrdersResponse | undefined): OrderRow[] {
  return res?.orders ?? res?.items ?? res?.results ?? res?.data ?? [];
}

export function formatMinor(minor?: number, currency?: string) {
  if (minor === undefined || minor === null) return "—";
  const symbol = currency === "USD" ? "$" : currency === "INR" ? "₹" : "";
  return `${symbol}${(minor / 100).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}
