# Refund Flow Console

Build a single-screen Refund Review Console using React 18, Vite, Tailwind CSS, and TanStack Query (@tanstack/react-query v5).
API Base URL: http://localhost:8000/api

Layout & Components:

1. MetricBar Component:
   - Call GET /api/metrics/summary.
   - Display summary cards for INR (₹) and USD ($) showing:
     * Formatted currency string (amount_formatted)
     * Minor unit value indicator (amount_minor in paise/cents)
     * Pending count (count)

2. QueueTable Component:
   - Call GET /api/orders with params: view ('finance' | 'support'), search, page, per_page.
   - Tabs:
     * 'Finance Outflow Queue' (view=finance, default)
     * 'Support History View' (view=support)
   - Real-time search bar updating the 'search' query parameter (filters by order_id or customer_id).
   - High-density table columns: Order ID, Customer ID, Total Paid, Refunded Succeeded, Pending Payout, Status, Flags.
   - Render Warning Pills from flags object:
     * is_high_value -> ⚠️ High Value
     * is_over_refunded -> ⚠️ Over-refunded
     * has_chargeback -> 🚨 Double Loss Risk
     * has_currency_mismatch -> ⚠️ Currency Mismatch
     * is_orphan_order -> ⚠️ Missing Order
   - Clicking a row opens the OrderDetail modal for that order_id.

3. OrderDetail Modal Component:
   - Call GET /api/orders/{order_id}.
   - Render warning banners at the top of the modal if warnings array is non-empty.
   - Render a vertical chronological timeline of items from the timeline array:
     * Badge colors based on type: refund.requested (yellow), refund.succeeded (green), refund.failed (red), chargeback.opened (purple).
     * Show occurred_at_utc, amount_minor, refund_id, source, and reason.
   - If an event is `refund.requested` and that refund's final derived status is still `pending`, display an 'Action Decision' button opening ActionDialog.

4. ActionDialog Component:
   - Popover/Modal to approve or reject a refund:
     * Actions: 'approve' or 'reject' buttons.
     * Required textarea for 'reason'.
   - On submission, generate one client-side `idempotency_key` per modal session using `crypto.randomUUID()`.
   - POST to /api/refunds/{refund_id}/decision with body: { action, reason, idempotency_key }.
   - Double-Click Safety: Disable the submit button immediately upon click and show a spinner.
   - On success, close dialog and invalidate TanStack Query keys ('orders', 'metrics-summary', 'order-detail').

Design Requirements:
- Single-page layout (no react-router page navigation).
- Professional slate/indigo dark/light theme designed for internal finance operations.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/21b9b4ea-b939-4782-bcd4-23ea5026b952).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
