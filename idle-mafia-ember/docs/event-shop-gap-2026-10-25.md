# Event Shop evidence gap — 2026-10-25

> **Implementation update, October 27:** earned-only acquisition now has current source/attribute adapter, separate default-off offer/reserve/spend/attempt settings, flat planner/capture/evidence and exact three-argument call description. Fifteen focused cases and an App/native-adapter scenario pass. Mixed paid/earned debit ordering remains unproven. Real source binding, durable usage/recovery and reservations are Task 24; whole C/T/L remains open. See [Event Shop evidence](m14-event-shop.md). The historical missing-source request below is superseded.

> **Superseded source-coverage claim, October 27:** the old export was filtered. The supplied place contains `EventShopTab-5c8d001aae45.lua` and `EventShop-dd4873a000cf.lua`, now in primary `imports/idle-mafia-2026-10-27-all-sources/`. Offers, medal-origin rules and `EventShopAction("buy", offer.key, 1)` are available. Implement from these sources before requesting another source sample. C/T/L remain incomplete until implementation, wiring and verification; the historical observation request below is not a current blocker. See `source-coverage-2026-10-27.md`.

`eventShop` remains C/T/L incomplete. The saved 0.26.530 place source
review recorded in `src/tabs/events/EventShopBlocked.luau` omits
`EventShopTab` and its offer definitions. The supplied Cobalt log audit
in `remote-log-audit-2026-10-25.md` has no Event Shop quote or purchase
transaction. `docs/native-reuse-audit.md` describes the intended selected
medal purchase but does not establish actual arguments or outcome fields.
These sources cannot support a safe purchase planner, call or evaluator.

Smallest needed current-client observation: the Event Shop's source
module/config for offer IDs, current price, event window, medal balance
and currency origin restrictions; one ordinary selected-item UI purchase
call with exact remote, arguments and reply; and before/after full Syncs
showing item/currency deltas and bought marker. A read-only catalog/Sync
sample is enough to implement the reader and settings first. Do not guess
remote arguments or use paid-origin medals until the source contract is
known.

`briefcases` is separate and locally complete: free-only action,
`source="free"` reply, one free-pick decrement and exact board reveal.
