# Briefcase current-source integration

The former runtime had a free-pick reader/planner/evidence path, but no binding or
tab adapter supplied its required event/rules facts. Its unit tests supplied those
facts manually. This was a missing integration independently of event availability.

The privately reviewed current PlaceVersion 654 `BriefcasesTab` checks replicated
MW `GlobalCaseEnd` against `ServerClock.now()` and obtains its season from
`GlobalCaseSeason`. `BriefcaseRules.VERSION` changes through the game's own
configuration application. The native request is
`BriefcaseAction:InvokeServer("open", index)`; no free-only argument exists.

`NativeClientBindings` now optionally captures these exact modules and their
current local-player/State/MW ownership. The Events source attaches a matching
full-Sync proof, takes its rules version from the current native module, and
checks the real current board, free count and selected unopened slot again before
dispatch. Event end, season/config changes, consumed free picks, changed boards,
replaced sources, partial Syncs and closed owners refuse emission. A missing
adapter cannot authorize caller-supplied event facts. The adapter does not call
native configuration application, predict prizes, open keys, or manufacture an
event. The native server still chooses the payment source at execution; local
checks cannot make that server operation atomic with unrelated manual play.

Exact successful free replies still require a newer matching native free-count
decrement and selected reveal. The native UI also accepts a `cleared` reply and
waits for `result.board + 1`; golden prizes can clear before all twelve reveals.
Evidence now handles that case only with the exact old-board cleared/free reply,
one newer empty next board, unchanged native season/config, and one free decrement.
Other board changes remain unconfirmed. Recovery retains the source facts/proof
and original baseline; it does not resend uncertain actions.

Admission requires an active event, but settlement of an already-sent pick can
arrive after expiry. When native event attributes disappear, the original saved
active source proof plus a matching current inactive proof and a genuine Sync
after the saved end time can still establish the exact debit/reveal. A new season,
wrong board, missing proof or changed source does not establish settlement. This
observation path never grants permission to open another case.
Pending, rate-limited, busy and presence callbacks remain unconfirmed before
either reveal or board-clear handling; a negative transient callback cannot
release an uncertain attempt as a terminal rejection.

The current live capture has no `GlobalCaseEnd` or `GlobalCaseSeason` attributes.
Its stored October board and free count are historical, so the event is inactive.
No live free pick is justified or claimed. A future active event still requires
a bounded live check and native outcome verification. The optional binding is
enabled only for the reviewed 654 layout; 655 needs separate source review.

Verification: new source and real Events/engine/broker/adapter/checkpoint tests
witnessed missing-source and missing-wiring failures before implementation. The
focused source, free-pick, entry/host, native binding, composition and recovery
suite passed 48 tests and 127 subtests. Coverage includes a consumed free pick
between queueing and dispatch (zero calls), native module replacement, missing or
expired event attributes, exact free reveal confirmation, and cleared-board
confirmation/refusals. Offline tests do not establish an active live event.
After the independent expiry and callback lifecycle fixes, the integrated full
suite passed 959 tests and 538 subtests, with one optional Luau analyzer skip.
