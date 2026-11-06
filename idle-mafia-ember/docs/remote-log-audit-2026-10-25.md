# October 25 Cobalt remote-log audit

Source: the user-supplied `2026-10-25T01_23_27Z.log` (174,661,872 bytes).
This is a passive native-client trace. Logged calls were from `MWClient`
(`IsExecutor=false`), so a successful reply does not prove the executor's
direct call shape or a durable saved outcome. Cobalt-generated replay code,
the client's first wire argument, account data, and session values were not
copied or executed. No MCP or live client call was made for this audit.

| Area | Observed native calls | Evidence and implementation consequence |
| --- | --- | --- |
| Operations | Three `CollectOperation(1)` and three `StartOperation("op_saltroad")` | All six replies report `ok=true`. Adjacent full Syncs show three ready runs with native slots 1, 2, 3 collected in turn, then the same operation started into slots 1, 2, 3. The collection *array index* shifts after each removal, but the native slot persists. Local start/collect evidence now requires unique native slots, exact count changes, and selected slot addition/removal. No executor-origin Operation call was captured. |
| Heists and Favors | Sixteen `HeistAction("board")`, thirteen `HeistAction("help", sequence)`, one `HeistAction("start", "heist_cistern", 10)` | The start reply reports `ok=true`; a later board contains `mine`. Help replies report `ok=true` with rewards. Board rows have `id`, `heistId`, `ownerId`, `endsAt`, `friend`, `famRel`, `helpsUsed`, and `sabosUsed`. This interval has no ledger/status recovery call; the start and help sequence values overlap, so the trace does not establish a safe shared sequence allocator. Mutations remain gated. |
| Ordinary Boss | Four `BossAction("stageAttack", stage)` calls, stages 1–4 | Replies report `ok=true`, `won=true`, `killed=true`. These are native calls, not recode sends. The user's Territory-war no-stamina constraint still blocks live Boss testing. |
| Shop | Twelve `BuyShopItem(itemId, nil, quotedCost)` calls | Replies report `ok=true`. The call shape matches the existing three-argument plan after the client's wrapper. The previous Shop state/evidence corrections remain offline only. |
| Black Market | One browse, one RAP, two prices, three mine, one rent, two list | All replies report `ok=true`; rent reports a 12-hour shop opening and list reports success. Cobalt's `n = 5` for `prices` includes the wrapper and two trailing nil arguments: the post-wrapper request is `("prices", itemId, nil, nil)`. The price reply's `item` matches the request, `day` is an eight-digit **string**, and `recent` rows carry prices. `MarketPrices` now keeps the observed four-argument call shape and validates the item/date response. The browse reply gives `more=true` without a page count; `MarketBrowse` now derives a bounded next-page hint from it. RAP sends a batch of 20 item IDs after `"rap"`, with two trailing nils; the reply maps each ID to `quantity`, `sales`, `average`, and `available`. A tab-local `MarketRap` reader now validates and caches that shape offline. Listing and rent change inventory or Gold and remain outside the live allowlist. |
| Other | `ContractAction("claim", 3)`, `ClaimLadder(2)`, `AllocateSkillPoint("stamina", 2)` | Each is a native call with `ok=true` reply. The stamina allocation was user action in the trace; no automation sent or replayed it. Family and Territory traffic also appears but gives no executor-origin proof. |

The trace cannot reveal server-side validation, generalize to future game
versions, or prove that every feature is complete. The only executor-origin
gameplay outcome established by the supplied Cobalt logs remains the three
earlier direct Job completions documented in the October 24 audit. Current
work is local source and tests; the published commit-pinned runtime is still
at `9da6d31` with Jobs and ordinary Boss in its send allowlist. No updated
manifest or loadstring was published for these corrections.

The three native Market `mine` replies carry only `ok=true` with no listing
rows or ownership identity. Listing status therefore needs a fresh native
Sync, not inference from the `mine` reply. Both captured `prices` replies
have 14 daily rows and 20 recent rows, within the reader's bounds. Across
the two native `list` actions, adjacent full Syncs show the account's
`market.listings` map growing 0→1 and 1→2; the listing rows carry item,
quantity, price, remaining quantity, creation time, and item-origin custody.
These native transitions inform future listing evidence but do not establish
executor acceptance or authorize automatic inventory custody changes.
The captured rows use `state="live"`. The offline `MarketListEvidence`
contract now requires that exact new listing plus an exact loose-inventory
decrease in a newer full Sync; it does not send or enable listing.

The single native rental sent `MarketAction("rent", 1, nil, nil)` after the
client wrapper. Its reply was `ok=true` with a 12-hour shop message. Nearby
full Syncs show loose `gold_bar` falling 54→53, bound `gold_bar` staying 28,
and `shopUntil` moving from an expired value to about 12 hours after the
newer `serverNow`. This is one native transition, not executor acceptance or
proof of all rental tiers. Any future rental evidence must check both the
exact Gold spend and the newer expiry, and preserve a separate spend cap.
