# Source coverage correction — October 27

The historical `idle-mafia-2026-10-11-full` export was a selected-name export. Its absence of a module did not establish that the supplied place save lacked that module. Do not repeat an absence claim from that folder without checking the complete manifest.

The supplied `C:/Users/asato/Downloads/GameSave_73897506680154.rbxl` was re-read as binary data with the existing `inspect_rbxm` reader. No saved script was executed. The extractor now has an explicit `--all-scripts` option; default/selected-name behavior is preserved. All **278** nonempty, uniquely named/hashed saved script sources were extracted to the primary workspace's `imports/idle-mafia-2026-10-27-all-sources/`, with a manifest. Extracted `GameVersion` is **0.26.530**; this is not a current-client version claim.

Recovered sources include:

| Source | Replaces earlier assumption |
| --- | --- |
| `CrewRecall-805e20839f28.lua` | Recall calls and deployment identity are available: `TerritoryAction("recallcrew", requestId, targets)` and `TerritoryStatus("recallstatus", requestId, nil)`. Native request IDs are monotonic epoch milliseconds; exact targets carry own user/slot, duty token or duty time, district and member identity. Durable ownership/recovery still needs implementation and Task 24 integration. |
| `TerritoryBonusDisplay-af7f2185b4e1.lua` | Holder bonus display uses `derived.territoryBonusSources`, with `known`, `familyId`, per-kind `total`, `active` and `inactive`; residency identity is `derived.residency.d`. |
| `EventShopTab-5c8d001aae45.lua` and `EventShop-dd4873a000cf.lua` | Event Shop's purchase call and offer catalog exist. The visible call is `EventShopAction("buy", offer.key, 1)`; medal-origin rules are in these sources. The old missing-source blocker is superseded; audit and implement before release. |
| `CrewHealModal` / `HenchmanHealingRules` / `ConsumableRules` | Recheck the prior item-heal gap against these sources before calling its contract missing. |
| `DailyRewards` / `BriefcaseRules` | Recheck the earlier reward-effect gaps against complete source coverage. A source shape is still distinct from a verified live effect. |

Config, GameData and several tab hashes differ from the historical filtered export. Family donation/contribution signatures and relevant Config limits were checked against the new FamilyTab/Config and agree with the implemented scope. Audit each subsequent tab against the complete source first. Current-client L and server-only behavior remain separate evidence requirements. Keep the extracted game sources local; the recode manifest scans only `src/` modules.
