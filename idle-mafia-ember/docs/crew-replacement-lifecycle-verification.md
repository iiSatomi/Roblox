# Crew replacement lifecycle verification — November 6, 2026

Offline tests exercise the real CrewReplacement helper, transaction owner and
runtime. Composition tests also use the Crew tab, tab assembler, engine, broker,
resource reservations and native dispatch adapter. Their executor records calls
in memory; no live dismissal or hire was performed.

The composed path sends one explicitly permitted dismissal, observes its exact
empty slot, then sends only the original funded hire. Exact reply member, cash
debit and unchanged other roster rows are required before settlement. Missing
dismissal permission sends nothing.

Prepared/sent dismissal and hire stages retain custody and lose emission arms
after restart. An observed-empty stage can continue its original funded hire
without charging a second cycle. Pending and rejected hires retain custody and
spend until their specific recovery conditions are met. Tests also cover exact
known-unsent restoration, ambiguous writes, stale writers and persistent caps.

Two failing regressions justified narrow product fixes:

- An unchanged rate-limited dismissal was classified as terminal rejection
  before reaching its existing rate-limit guard. That guard now runs first.
- Other pending cash exposure was counted without the replacement's reserve.
  Both dismissal funding and hire now require quote plus other holds plus the
  explicit cash reserve; exact boundary tests cover both stages.

The focused lifecycle/composition run passed 15 tests and 17 subtests. Live
acceptance remains unavailable here. The ordinary native dismissal has no
server-side member identity argument, and ongoing native Auto Roll is blocked.
