# Read-only weekly Family Takedown state

Status 2026-10-21: read-only view and optional Context integration
implemented; 303 Python/Lupa tests pass. Attack/claim actions remain
open.

The saved `FamilyBossView` requests
`FamilyBossAction:InvokeServer("state", "seen"|nil)` and displays
week, Family, stage, free charges, tickets and claim records. Its
`freeNow` formula regenerates charges from `nextFreeAt` and
`freeRegen` against native `serverNow`. Add a pure account/capture-
matched state view with bounded values and an exact week/Family key.
Never treat held Tickets as permission for automatic attacks.
Attack/claim intents and native transport remain separate future
slices; the current response shape is not live-verified.
