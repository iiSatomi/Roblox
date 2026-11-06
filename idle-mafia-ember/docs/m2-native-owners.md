# Native controller ownership context

The offline `Context` reader now separates saved controller activity from
entitlement for Jobs, Shop, Crew Auto Roll and city Boss Auto. All four require
an adapter-labelled complete Sync before activity is called active or inactive;
a partial Sync stays unknown. The scheduler yields only the matching domain
when its native activity is active or unknown. Entitlement by itself never
causes a hub action or proves a controller is running.

Saved client `0.26.487.1` evidence: `JobsTab` reads `derived.autoJobs` and
`autoJob` around lines 935–960; `AutoBuy` reads `derived.autoBuy` and
`autoBuyRules.on` around lines 80–110 and 540–565; `CrewTab` reads
`derived.autoRoll` and per-slot `autoRolls` around lines 1262–1270 and
3032–3050; `BossTab` reads `derived.autoBoss` and `bossStage.auto` around
lines 1970–1993. The city Boss client also has local loop state, so a saved
stage value cannot certify that its loop is currently alive. The complete
Sync label and current shapes must be verified by a future native adapter.

Malformed saved activity becomes unknown. A complete Sync with no saved
Jobs/Shop/Roll record, or no saved city Boss auto stage, is treated as
inactive according to the observed client defaults. Boss activity is limited
to city Bosses; it says nothing about Global Bosses, Takedown or PvP. The
reader does not start, stop, rent or unlock native controllers.

Local evidence: 107 Python/Lupa tests pass, including active/inactive/unknown
and matching-domain scheduler cases. Luau compile and both analyzers accept
the changed module. Economic/buff derivation, background-read budgeting and
current runtime shape validation remain open Task 5 work. This is saved
client evidence and synthetic state only, not live controller verification.
