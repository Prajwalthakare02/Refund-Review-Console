# Take-Home Assignment

**Full Stack Developer (Entry Level) · Two Theta**
**Build: the Refund Review Console**

**Time:** aim for **4–6 hours**. A smaller, correct, well-reasoned build beats a large broken one. We care more about your thinking than about how much you ship.

**Stack:** anything you're comfortable with. Any language, any framework, any database (or none). Share your work as a **GitHub repository**.

**AI tools:** use them freely — Claude, Copilot, Cursor, whatever you like. We use them every day and we expect you to. See *Ground rules on AI* at the end; there is one deliverable attached to this.

---

## The situation

One of our clients is an online retailer. Their support agents currently handle refunds by opening three different systems and a spreadsheet. Refunds are now their top source of customer complaints, and their finance team writes off a number every quarter that nobody can fully explain.

They've asked for a small internal tool — a **Refund Review Console** — that gives an agent one screen with a trustworthy answer to: *what is the state of this refund, and what can I still do about it?*

We've been given a **two-week export** from their payment stack and an **email thread** with three of their people. That is all the specification that exists. Nobody at the client is available to answer follow-up questions during this assignment — that is deliberate, and it is part of the exercise.

---

## What you're given

Two files, in `refund-console-data/`:

**`orders.csv`** — one row per order.

| column | notes |
|---|---|
| `order_id` | |
| `customer_id` | |
| `currency` | |
| `total_amount` | what the customer paid for the order |
| `placed_at` | |
| `channel` | web / ios / android |
| `region` | |

**`events.jsonl`** — one JSON object per line, the payment stack's event feed. Types you'll see include `refund.requested`, `refund.succeeded`, `refund.failed` and `chargeback.opened`. Fields include `event_id`, `refund_id`, `order_id`, `amount_minor`, `currency`, `occurred_at`, `received_at` and `source`.

There is no data dictionary beyond the above, and no schema guarantee. **Reading the data carefully is part of the assignment.** The export is real-shaped: it came out of a production system that has been running for four years and has been through two gateway migrations.

**Pin "now" to `2026-08-11T10:00:00+05:30`** so your output is reproducible. Don't use the wall clock.

---

## The email thread (this is the spec)

> **From: Priya (Finance Lead)**
> The queue should only show refunds where money can still move. Anything that's already been paid out is noise for my team — we're trying to control outflow, not read history.
> Also, anything high value needs my approval before it goes out. Please flag those separately.
> And give me one number I can trust at the top of the screen: total pending payout right now. I look at that number every morning.

> **From: Rahul (Support Lead)**
> Respectfully, no. My agents need to see *everything* the customer has raised in the last week, including the ones already refunded — otherwise when someone calls asking "where is my money", we're back to opening three systems. That's the whole reason we asked for this.
> Also the current internal page hangs sometimes and agents click Approve twice. I don't know what that does on your side but it can't be good.

> **From: Meena (Ops)**
> Two things from my side. Our legacy gateway posts in our local time (Hyderabad) and it isn't as consistent as the new one. And if the overnight relay job fails, it replays the whole day's events the next morning — I've raised it, it's not getting fixed this quarter.
> Also to set expectations: what we've sent you is a two-week sample. Production is roughly 40M events a month.

> **From: Priya (Finance Lead)**
> One more. If the numbers on this screen don't match what my team sees in the ledger, they will stop using it within a week. Whatever you build, I need to be able to tell where a number came from.

---

## What to build

### Part A — Get the state right (required)

From `orders.csv` and `events.jsonl`, derive, per order, the truthful current state: what has actually been refunded, what is still in flight, and how much (if anything) can still be refunded.

This is the core of the assignment and where most of your time should go. The event feed is the messy part. **Decide what your rules are, write them down, and make sure your code and your written rules agree.**

### Part B — The console (required)

A working, minimal full-stack surface. Not a design exercise — plain HTML and a table is completely fine.

- **A queue view** — the list an agent works through, with whatever filters and columns your reading of the email thread justifies.
- **A detail view** — one order, its refund history, and the state you derived, in a form an agent could read out to a customer on the phone.
- **An action** — an endpoint plus a control that records a decision on a refund (approve / reject, with a reason). It does not need to move real money; recording the decision durably is enough.
- **The number Priya asked for**, at the top.

### Part C — Show your reasoning (required)

Three files in the repo:

- **`README.md`** — how to run it, and what it does.
- **`DECISIONS.md`** — the important one. Every judgement call you had to make because the spec didn't tell you, what you chose, what you gave up, and what would change your mind. Include the ones you decided *not* to handle, and why that's the right call for a 4–6 hour build.
- **`AI_USAGE.md`** — see *Ground rules on AI* below.

Plus **tests** — enough to convince us the state you derive in Part A is correct, including the cases you found interesting. Quality over count.

### Scope

Parts A, B and C are the whole assignment. There is no bonus round, and building beyond this does not score higher — **knowing where to stop is part of what we're assessing.** If you finish early, spend the time making Part A provably correct rather than adding features.

---

## What to submit

1. A **GitHub repository** link — public, or shared with the address in your invitation email.
2. **Commit as you go.** We read the commit history. One giant commit at the end tells us nothing about how you work, and we count it against you.
3. Optionally, a live demo link if you deployed it.

---

## Ground rules on AI

Use AI as much as you like. Every engineer here does. We are not testing whether you can work without it — we're testing whether **you were driving**.

So, in `AI_USAGE.md`, tell us:

1. **Where AI helped most**, and roughly how you used it (one-shot? iterating? did you give it the data?).
2. **Three times it was wrong, incomplete, or confidently misleading** — what it produced, how you noticed, and what you did instead. If you genuinely hit zero, say so and tell us how you checked.
3. **One decision you made against the AI's suggestion**, and why you were right (or why you're still not sure).
4. **How you verified the output** — not "I read it", but the specific thing you ran or checked that would have caught a mistake.

Be honest. "I pasted the schema in, got a working ingest, then found it double-counted and rewrote that part myself" is a **strong** answer. A polished document with no friction in it reads as either untrue or as a sign you never looked closely, and both score badly.

We will ask you to modify your own submission live in the interview. Build accordingly.

---

## How we evaluate

| | |
|---|---|
| **Correctness of derived state** | Does the number you show actually match what the events say happened? |
| **Judgement under ambiguity** | The spec conflicts with itself and the data doesn't match the spec. What did you decide, and did you notice you were deciding? |
| **Reading comprehension** | Everything you needed was in the brief, the thread, or the data. Did you find it? |
| **Honest scope** | Knowing what to leave out, and saying so, scores higher than a half-finished everything. |
| **AI fluency** | Speed *and* skepticism. Using AI well means catching it when it's wrong. |
| **Clarity** | Readable code, a README that works, a `DECISIONS.md` we could hand to the client. |

One thing worth saying plainly: **we would rather see a small console that is right about a hard case than a beautiful one that is quietly wrong.** If you find something in the data that doesn't add up, that finding — written down — is worth more to us than another feature.

Good luck. We're looking forward to reading it.
