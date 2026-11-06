# Read-only Black Market browse staging

`MarketBrowse` stages one `all`, saved group, or item scope page from
the saved `MarketTab` shape `MarketAction("browse", kind, arg, page)`.
For all-scope reads the third argument is `nil`. The source
for client 0.26.487.1 forwards four arguments through its `invoke`
helper, and saved config caps browse pages at five. The future query
executor must unpack through arity 4 so the interior `nil` survives.
This module does not call a remote.

`Prepare` issues a local token and invalidates earlier requests.
`Accept` rejects stale tokens, malformed replies, invalid pages and
unbounded, sparse or malformed listing rows. A successful reply consumes
its token so it cannot be accepted twice. Accepted listing fields are copied;
the result carries the source's `more`, `stale` and `small` flags without
claiming a listing, purchase or sale succeeded. `Close` invalidates
late replies. Rarity encoding, browse caching, bounded read-budget
scheduling, native response compatibility and actual UI wiring remain
open. The saved source is offline evidence, not live verification.

`MarketPrices` separately stages the saved
`MarketAction("prices", itemId, nil, nil)` query. It copies bounded
recent-sale and daily-average rows, fences superseded replies and uses
the saved client's 120-second local cache window. Cached prices are
observations, not a verified sale price or permission to buy/list.
Sparse history arrays are rejected instead of silently truncating rows.
An eventual shared read scheduler must honor both queries' four-argument
arity and keep them subordinate to gameplay requests.

`MarketReadRuntime` now composes both query modules with an injected
`ReadBudget` and executor. It queues only requested sources, permits one
read in flight, unpacks all four arguments explicitly and discards late
callbacks after close or budget timeout. A timed-out queued callback is
fenced before invoking; a call already invoking keeps the lane occupied
until it settles, and its late result is discarded. The fake executor tests prove
this scheduling boundary; no current Roblox remote or Ember control is
connected, and the caller must supply the real budget and event wiring.
