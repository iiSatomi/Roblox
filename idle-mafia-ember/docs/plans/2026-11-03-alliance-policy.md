# Alliance/Enemy implementation

User-approved direction: one Alliance/Enemy page, Alliances and Enemies sub-pages. These are local targeting preferences, not a game diplomacy treaty.

- [x] Typed profile preferences: up to 64 stable Family IDs per list; enemy mode Off/Prefer enemies/Enemies only. Ally wins overlap. Stop/unload keeps protection lists.
- [x] Apply protection before Combat/Scout ranking; enemy preference before high-value ranking, after safety. Existing own-Family/friend/war exclusion, costs, caps, consent and challenges remain.
- [x] Include relation preferences in the shared final dispatch selection token for all hostile lanes. Changes revoke queued work; sent work retains custody/evidence.
- [x] Read-only native FamilyAction browse/search through existing read coordinator, bounded replies, 60-second spacing, source/header/unload fences. Names are labels, IDs are selection identity. Never treat browse results as target membership proof.
- [x] Ember sub-page switcher and searchable picker; independent saved Ally/Enemy lists; explicit remove; profile roundtrip and stale/empty/error states.
- [x] Focused policy, actual App queue/unsent/sent, UI and directory tests; full suite for storage/tab changes; independent review. Report source/local/live/package separately.

War, sabotage and other blocked hostile lanes remain blocked. They must consume this policy before activation; no claim of their live protection. The directory is a partial native search, not an exhaustive census. No gameplay enabled by setting relations. Native manual challenges remain manual. Executable pins/publication unchanged.


Acceptance: 24 focused tests cover policy, actual App queuing/membership/custody, directory lifecycle/coordinator and UI. Independent review reproduced a final yield race; shared selection is now checked after native preflight returns. Production-shaped remote checks and reserved-ID validation are fixed. See tasks/todo.md for final full-suite and package evidence.

Live evidence: docs/native-alliance-directory-2026-11-03.json. The new query module accepted 182 current native rows and closed cleanly in an isolated read-only probe. Integrated UI/gameplay acceptance remains pending. The current Ember API has no nested Tab method; the page uses two explicit sub-page buttons and mutually visible groups, with supported Dropdown SetOptions silent updates (https://rbx.lol/docs/ember/controls/dropdown).
