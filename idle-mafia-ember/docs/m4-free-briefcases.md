# Free Briefcase picks: offline claim slice

Saved native `0.26.487.1` `BriefcasesTab` lines 95–149 reads native
season, free balance and board state alongside the live event season/end
attributes. Lines 1001–1059 call `BriefcaseAction:InvokeServer("open",
index)` for both free picks and key picks. `BriefcaseRules` defines 12
cases and `caseKey(i) == "c" .. i`. A successful reply reports `source`.
The client call alone cannot prove a free pick or prize delivery.

`FreeBriefcasesState` requires a fresh matching complete Sync, active
matching event, current board config, positive replicated free balance,
valid opened cases and an unopened case. It selects the first unopened
index without predicting a prize. `FreeBriefcases` is a separate
OFF-default opt-in and never intentionally proposes a key pick or
purchase. `FreeBriefcasesEvidence` requires a successful reply with
`source == "free"` plus a newer same-season, same-board full Sync
showing the selected case revealed and free balance decreased by one.
An event, rule or board change remains pending. A special prize that
immediately clears the board may therefore end as unconfirmed and enter
the broker's 45-second skip/cooldown; it is not counted as success.

The Briefcases panel can show shared fake-broker status. The distributed
inert Ember 0.1.1 bundle is unchanged. Local evidence: 187 Python/Lupa
tests, 12 Node tests, catalog check, new Luau compilation and both
analyzer modes pass. Standalone EmberAdapter analysis retains existing
Roblox-global/local-shadow diagnostics. Native adapter/event attribute
shape, actual server response, free-versus-key race behavior, prize
delivery and live gameplay remain unverified.
