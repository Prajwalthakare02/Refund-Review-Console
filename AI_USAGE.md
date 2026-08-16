# AI Usage Log

This project used AI as an implementation assistant. Every AI output was reviewed against the assignment, exercised on the actual data, and corrected when it diverged from the brief.

## 1) Where AI helped most

- Reading the raw refund data and turning it into concrete state rules.
- Scaffolding the backend endpoints, state engine, and React queue/detail views.
- Finding integration mismatches between the backend response shape and the frontend components.

## 2) Three times AI was wrong or incomplete

1. AI initially allowed `POST /api/refunds/{id}/decision` to accept decisions for refunds that were already `succeeded` or already manually decided. I caught it by exercising the endpoint against a settled refund and seeing the derived totals change incorrectly. I fixed it by adding a backend guard that returns `409` unless the refund is currently `pending`.
2. AI initially exposed the `Action Decision` button for any `refund.requested` timeline item, even when the refund's final derived state was already `succeeded` or `failed`. I noticed it by checking the detail view for an order whose refund chain had already settled. I fixed it by gating the UI on the refund's final derived status, not just the raw event type.
3. AI initially modeled the support queue too broadly by including recently placed orders with no refund activity. I caught it by comparing the brief's wording against actual support queue membership and finding orders that had no customer-raised refund activity. I fixed it by requiring refund or chargeback activity within the 7-day window.

## 3) One decision I made against AI’s suggestion

- I kept the finance queue as a pending-only actionable queue instead of turning it into a combined history view. The brief has an explicit tension between Finance and Support, and Priya's requirement is operational control of outflow, not audit history. Support history handles the broader visibility requirement.

## 4) How I verified the output

- Ran `pytest -q backend/tests` after each state-engine and decision-flow change.
- Ran `npm run lint`, `npx tsc --noEmit`, and `npm run build` in `frontend` after UI and query-key changes.
- Checked live API behavior for queue membership, decision status, and pinned time through the actual endpoints.
- Cross-checked the final rules in `DECISIONS.md` against the implemented behavior and the assignment brief.
