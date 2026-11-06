"""Explicit ordinary Heist sabotage with exact row and daily guards."""
import unittest

from engine_harness import Harness, lua_table


class SabotageTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.context = self.h.load("src/game/Context.luau").new(
            self.h.contracts, None, None,
            self.h.load("src/game/HeistBoardState.luau"))
        self.reader = self.h.load("src/game/SabotageState.luau")
        self.planner = self.h.load("src/features/Sabotage.luau")
        self.evidence = self.h.load("src/features/SabotageEvidence.luau")

    def raw(self, revision=1, owner=99, friend=False, relation=None,
            helps=0, sabos=0, favors=12, attempts=0, energy=20,
            row_id="run-1"):
        now = 2000000
        return self.h.snapshot(revision=revision,
            native={"fullSync": True, "serverNow": now,
                    "family": {"id": "own-family"}, "level": 20, "pools": {"energy": energy}},
            heistCatalog=[{"id": "h_a", "level": 10,
                           "stake": 100, "energy": 2}],
            heistBoardProof={"account": "user-a", "capturedAt": 0,
                "board": {"ok": True, "serverNow": now,
                    "rows": [{"id": row_id, "heistId": "h_a",
                        "ownerId": owner, "friend": friend,
                        "famId": "other-family", "famRel": relation, "helpsUsed": helps,
                        "sabosUsed": sabos, "endsAt": now + 300}],
                    "favorsLeft": favors, "saboFavorCost": 2,
                    "saboEnergyCost": 3, "saboMaxPerHeist": 5}},
            localUserIdProof={"account": "user-a", "capturedAt": 0,
                              "userId": 42},
            sabotageUsageProof={"account": "user-a",
                "capturedAt": 0, "day": now // 86400,
                "attempts": attempts})

    def proposal(self, raw):
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        view, reason = self.reader.read(raw, context)
        self.assertIsNone(reason)
        return self.planner.propose(view,
            lua_table(self.h.lua, {"enabled": True}),
            lua_table(self.h.lua, {"energy": 0,
                "uncertainEnergy": 0, "favors": 0,
                "uncertainFavors": 0}))

    def test_selects_nonfriend_and_confirms_exact_row(self):
        before = self.raw()
        proposal, reason = self.proposal(before)
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["rowId"], "run-1")
        self.assertTrue(proposal["intent"]["needsSequence"])
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        self.h.at(1)
        after = self.raw(revision=2, sabos=1, favors=10,
                         attempts=1)
        after["heistBoardProof"]["capturedAt"] = 1
        after["localUserIdProof"]["capturedAt"] = 1
        after["sabotageUsageProof"]["capturedAt"] = 1
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "confirmed")
        after["heistBoardProof"]["board"]["rows"][1]["ownerId"] = 100
        self.assertEqual(self.evidence.evaluate(proposal, before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "pending")

    def test_self_friend_family_help_and_cap_block(self):
        for changes in ({"owner": 42}, {"friend": True},
                        {"relation": "family"}, {"helps": 1},
                        {"attempts": 5}, {"favors": 6},
                        {"energy": 12}):
            with self.subTest(changes=changes):
                self.assertIsNone(self.proposal(
                    self.raw(**changes))[0])

    def test_numeric_row_id_is_preserved(self):
        raw = self.raw(row_id=731)
        proposal, reason = self.proposal(raw)
        self.assertIsNone(reason)
        self.assertEqual(proposal["intent"]["rowId"], 731)
        self.assertIn("number:731", proposal["actionKey"])
        self.assertIsNotNone(self.evidence.capture(proposal, raw)[0])

    def test_missing_identity_or_usage_blocks(self):
        raw = self.raw()
        raw["localUserIdProof"] = None
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        self.assertIsNone(self.reader.read(raw, context)[0])
        raw = self.raw()
        raw["sabotageUsageProof"]["day"] -= 1
        context = self.context.Read(self.context, raw,
            lua_table(self.h.lua, self.h.session), 0, 2)[0]
        self.assertIsNone(self.reader.read(raw, context)[0])

    def test_fractional_board_clock_keeps_sabotage_evidence(self):
        before = self.raw()
        before["native"]["serverNow"] += 0.25
        before["heistBoardProof"]["board"]["serverNow"] += 0.5
        proposal, reason = self.proposal(before)
        self.assertIsNone(reason)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        self.assertEqual(baseline["rowId"], "run-1")


    def test_nonterminal_replies_retain_unresolved_outcome(self):
        before = self.raw()
        proposal, reason = self.proposal(before)
        self.assertIsNone(reason)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        replies = [
            {"pending": True},
            {"code": "pending"},
            {"code": "no_pending"},
            {"code": "rate_limited", "retryIn": 3},
            {"code": "presence"},
            {"code": "presence", "presence": {}},
            {"code": "presence", "presence": {"kind": "heists",
                                              "until": 2000300}},
        ]
        for advanced in (False, True):
            after = self.raw(revision=2, favors=10 if advanced else 12,
                             sabos=1 if advanced else 0, attempts=1)
            for reply in replies:
                for ok in (False, True):
                    envelope = {"ok": ok, **reply}
                    with self.subTest(advanced=advanced, reply=envelope):
                        self.assertEqual(self.evidence.evaluate(proposal,
                            before, after, lua_table(self.h.lua, envelope),
                            baseline), "pending")

    def test_terminal_rejection_preserves_exact_effect_guard(self):
        before = self.raw()
        proposal, reason = self.proposal(before)
        self.assertIsNone(reason)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        rejected = lua_table(self.h.lua, {"ok": False, "code": "rejected"})
        self.assertEqual(self.evidence.evaluate(proposal, before,
            self.raw(revision=2, attempts=1), rejected, baseline),
            "rejected")
        self.assertEqual(self.evidence.evaluate(proposal, before,
            self.raw(revision=2, favors=10, sabos=1, attempts=1),
            rejected, baseline), "pending")


    def with_known_resources(self, raw, cash=1000, xp=100, energy=20):
        native = raw["native"]
        for name, value in {"cash": cash, "xp": xp, "banked": 200,
                            "respect": 5, "skillPoints": 2}.items():
            native[name] = value
        native["pools"]["energy"] = energy
        native["pools"]["health"] = 80
        native["pools"]["stamina"] = 40
        for name, value in {
            "stats": {"maxHealth": 100, "attack": 10},
            "inventory": {"restorative": 2},
            "inventoryBound": {"restorative": 1},
            "collection": {"w_policebaton": 1},
            "collectionBound": {"w_policebaton": 1},
        }.items():
            native[name] = lua_table(self.h.lua, value)
        return raw

    def protocol_proof(self, raw, counter, quote=False):
        proof = {name: raw[name] for name in (
            "session", "account", "place", "release", "revision", "capturedAt")}
        proof.update(nativeJob="job-a", nativeEpoch="epoch-a",
                     nativeSourceKey="a" * 64, controllerCounter=counter)
        if quote:
            proof["quote"] = {"sequence": counter + 1,
                "nativeJob": "job-a", "nativeEpoch": "epoch-a",
                "nativeSourceKey": "a" * 64}
        raw["heistProtocolProof"] = lua_table(self.h.lua, proof)
        return raw

    def recovery_case(self, ok=True, native=False):
        before = self.with_known_resources(self.raw(revision=7))
        proposal, reason = self.proposal(before)
        self.assertIsNone(reason)
        if native:
            for name, value in {"sequence": 5, "nativeJob": "job-a",
                    "nativeEpoch": "epoch-a",
                    "nativeSourceKey": "a" * 64}.items():
                proposal["intent"][name] = value
            self.protocol_proof(before, 4, quote=True)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        after = self.with_known_resources(
            self.raw(revision=0, favors=10 if ok else 12,
                     sabos=1 if ok else 0, attempts=1),
            cash=1000 + (0 if ok else 0),
            xp=150 if ok else 100, energy=17 if ok else 20)
        after["session"] = "run-b"
        after["native"]["serverNow"] = 2000001
        after["heistBoardProof"]["board"]["serverNow"] = 2000001
        if native:
            self.protocol_proof(after, 5)
        reply = {"ok": True, "cash": 0, "xp": 50} if ok else {
            "ok": False, "code": "rejected"}
        data = lua_table(self.h.lua, {"proposal": proposal, "before": before,
                                    "baseline": baseline, "reply": reply})
        return data, after

    def test_rejection_requires_newer_unchanged_known_state(self):
        changes = [
            (("native", "pools", "energy"), 19),
            (("native", "pools", "health"), 79),
            (("native", "pools", "stamina"), 39),
            (("native", "cash"), 1001),
            (("native", "xp"), 101),
            (("native", "level"), 21),
            (("native", "banked"), 201),
            (("native", "respect"), 6),
            (("native", "skillPoints"), 3),
            (("native", "stats", "attack"), 11),
            (("native", "inventory", "restorative"), 1),
            (("native", "inventoryBound", "restorative"), 0),
            (("native", "collection", "w_policebaton"), 0),
            (("native", "collectionBound", "w_policebaton"), 0),
            (("native", "cash"), None),
            (("native", "fullSync"), False),
            (("heistBoardProof", "board", "favorsLeft"), 11),
            (("heistBoardProof", "board", "rows", 1, "ownerId"), 777),
            (("heistBoardProof", "board", "rows", 1, "heistId"), "other"),
            (("heistBoardProof", "board", "rows", 1, "endsAt"), 2000301),
            (("heistBoardProof", "board", "rows", 1, "sabosUsed"), 1),
            (("heistBoardProof", "board", "rows", 1, "helpsUsed"), 1),
            (("heistBoardProof", "board", "saboEnergyCost"), 99),
            (("heistBoardProof", "board", "mine"), {"id": "other"}),
            (("sabotageUsageProof", "attempts"), 0),
            (("sabotageUsageProof", "attempts"), 2),
            (("revision",), 7),
            (("capturedAt",), -1),
            (("native", "serverNow"), 1999999),
            (("heistBoardProof", "board", "serverNow"), 1999999),
        ]
        for path, value in changes:
            data, after = self.recovery_case(ok=False)
            after["session"], after["revision"] = "run-a", 8
            current = after
            for field in path[:-1]:
                current = current[field]
            current[path[-1]] = lua_table(self.h.lua, value)
            with self.subTest(path=path):
                self.assertEqual(self.evidence.evaluate(data["proposal"],
                    data["before"], after, data["reply"], data["baseline"]),
                    "pending")

    def test_saved_terminal_outcomes_recover_across_session_revision_reset(self):
        self.assertTrue(callable(self.evidence["recoverSaved"]))
        for ok, expected in ((True, "confirmed"), (False, "rejected")):
            data, after = self.recovery_case(ok=ok)
            with self.subTest(ok=ok):
                self.assertEqual(self.evidence.recoverSaved(data, after), expected)

    def test_saved_recovery_requires_exact_original_capture_and_exposure(self):
        self.assertTrue(callable(self.evidence["recoverSaved"]))
        changes = [
            (("baseline", "favorsBefore"), 999),
            (("before", "native", "cash"), 999),
            (("proposal", "resources", "energy"), 99),
            (("proposal", "resources", "favors"), 99),
            (("proposal", "resources", "cash"), 1),
            (("proposal", "intent", "rowId"), "other"),
            (("proposal", "feature"), "other"),
            (("proposal", "actionKey"), "other"),
        ]
        for path, value in changes:
            data, after = self.recovery_case()
            current = data
            for field in path[:-1]:
                current = current[field]
            current[path[-1]] = value
            with self.subTest(path=path):
                self.assertIsNone(self.evidence.recoverSaved(data, after))

    def test_saved_recovery_holds_unknown_reply_or_changed_known_outcome(self):
        self.assertTrue(callable(self.evidence["recoverSaved"]))
        for reply in (None, {"ok": False, "pending": True},
                {"ok": False, "code": "pending"},
                {"ok": False, "code": "no_pending"},
                {"ok": False, "code": "rate_limited"},
                {"ok": False, "code": "presence", "presence": {}}):
            data, after = self.recovery_case()
            data["reply"] = lua_table(self.h.lua, reply)
            with self.subTest(reply=reply):
                self.assertIsNone(self.evidence.recoverSaved(data, after))
        for ok in (False, True):
            for path, value in [
                (("account",), "other"),
                (("place",), "other"),
                (("release",), "other"),
                (("session",), ""),
                (("revision",), -1),
                (("native", "serverNow"), 2000000),
                (("heistBoardProof", "board", "serverNow"), 2000000),
                (("heistBoardProof", "board", "serverNow"), 2086400),
                (("heistBoardProof", "query"), "other"),
                (("native", "fullSync"), False),
                (("native", "cash"), 999),
                (("native", "xp"), 999),
                (("native", "level"), 21),
                (("native", "pools", "energy"), 19),
                (("native", "inventory", "restorative"), 1),
                (("heistBoardProof", "board", "rows", 1, "ownerId"), 777),
                (("sabotageUsageProof", "attempts"), 0),
                (("sabotageUsageProof", "attempts"), 2),
            ]:
                data, after = self.recovery_case(ok=ok)
                current = after
                for field in path[:-1]:
                    current = current[field]
                current[path[-1]] = value
                with self.subTest(ok=ok, path=path):
                    self.assertIsNone(self.evidence.recoverSaved(data, after))

    def test_native_scope_and_allocated_counter_guard_outcomes(self):
        self.assertTrue(callable(self.evidence["recoverSaved"]))
        for ok, expected in ((True, "confirmed"), (False, "rejected")):
            data, after = self.recovery_case(ok=ok, native=True)
            self.assertEqual(self.evidence.recoverSaved(data, after), expected)
            after["heistProtocolProof"]["controllerCounter"] = 6
            self.assertEqual(self.evidence.recoverSaved(data, after), expected)
            for field, value in (
                ("nativeJob", "other"), ("nativeEpoch", "other"),
                ("nativeSourceKey", "b" * 64), ("controllerCounter", 4),
                ("session", "other"), ("revision", 99), ("capturedAt", 99),
            ):
                data, after = self.recovery_case(ok=ok, native=True)
                after["heistProtocolProof"][field] = value
                with self.subTest(ok=ok, field=field):
                    self.assertIsNone(self.evidence.recoverSaved(data, after))
            data, after = self.recovery_case(ok=ok, native=True)
            after["heistProtocolProof"] = None
            self.assertIsNone(self.evidence.recoverSaved(data, after))

    def test_capture_refuses_changed_native_quote_scope(self):
        for path, value in [
            (("nativeJob",), "other"), (("nativeEpoch",), "other"),
            (("nativeSourceKey",), "b" * 64), (("controllerCounter",), 5),
            (("quote", "sequence"), 6), (("quote", "nativeEpoch"), "other"),
            (("session",), "other"),
        ]:
            data, _ = self.recovery_case(native=True)
            proof = data["before"]["heistProtocolProof"]
            current = proof
            for field in path[:-1]:
                current = current[field]
            current[path[-1]] = value
            with self.subTest(path=path):
                self.assertIsNone(self.evidence.capture(data["proposal"],
                    data["before"])[0])


    def test_signed_native_row_data_remains_valid_owned_evidence(self):
        data, _ = self.recovery_case(ok=False)
        before = data["before"]
        before["heistBoardProof"]["board"]["rows"][1]["net"] = -5
        before["native"]["stats"]["temporaryDefense"] = -2
        baseline, reason = self.evidence.capture(data["proposal"], before)
        self.assertIsNone(reason)
        after = self.with_known_resources(self.raw(revision=8, attempts=1))
        after["native"]["stats"]["temporaryDefense"] = -2
        after["heistBoardProof"]["board"]["rows"][1]["net"] = -5
        self.assertEqual(self.evidence.evaluate(data["proposal"], before,
            after, data["reply"], baseline), "rejected")

    def test_native_live_outcome_uses_owned_proof_and_exact_known_resources(self):
        for ok, expected in ((True, "confirmed"), (False, "rejected")):
            data, after = self.recovery_case(ok=ok, native=True)
            after["session"], after["revision"] = "run-a", 8
            self.protocol_proof(after, 5)
            header = lua_table(self.h.lua, {name: data["before"][name]
                for name in ("session", "account", "place", "release",
                             "revision", "capturedAt")})
            self.assertEqual(self.evidence.evaluate(data["proposal"], header,
                after, data["reply"], data["baseline"]), expected)
            for path, value in [
                (("native", "cash"), 999),
                (("native", "xp"), 999),
                (("native", "level"), 21),
                (("native", "pools", "energy"), 19),
                (("heistProtocolProof", "nativeJob"), "other"),
                (("heistProtocolProof", "nativeEpoch"), "other"),
                (("heistProtocolProof", "nativeSourceKey"), "b" * 64),
                (("heistProtocolProof", "controllerCounter"), 4),
            ]:
                data, after = self.recovery_case(ok=ok, native=True)
                after["session"], after["revision"] = "run-a", 8
                self.protocol_proof(after, 5)
                current = after
                for field in path[:-1]:
                    current = current[field]
                current[path[-1]] = value
                with self.subTest(ok=ok, path=path):
                    self.assertEqual(self.evidence.evaluate(data["proposal"],
                        header, after, data["reply"], data["baseline"]),
                        "pending")

    def test_saved_recovery_requires_unambiguous_complete_target_rows(self):
        for kind in ("duplicate", "sparse", "missing"):
            data, after = self.recovery_case()
            rows = after["heistBoardProof"]["board"]["rows"]
            if kind == "duplicate":
                rows[2] = rows[1]
            elif kind == "sparse":
                rows[3] = rows[1]
            else:
                rows[1] = None
            with self.subTest(kind=kind):
                self.assertIsNone(self.evidence.recoverSaved(data, after))

    def test_saved_legacy_outcome_compares_only_original_known_resources(self):
        before = self.raw(revision=7)
        proposal, reason = self.proposal(before)
        self.assertIsNone(reason)
        baseline, reason = self.evidence.capture(proposal, before)
        self.assertIsNone(reason)
        after = self.raw(revision=0, favors=10, sabos=1, attempts=1)
        after["native"]["pools"]["energy"] = 17
        after["session"] = "run-b"
        after["native"]["serverNow"] = 2000001
        after["heistBoardProof"]["board"]["serverNow"] = 2000001
        data = lua_table(self.h.lua, {"proposal": proposal, "before": before,
            "baseline": baseline, "reply": {"ok": True}})
        self.assertEqual(self.evidence.recoverSaved(data, after), "confirmed")


    def native_regen_case(self, crossing=False):
        data, after = self.recovery_case(native=True)
        before = data["before"]
        before["native"]["maxLevel"] = 20
        before["heistProtocolProof"]["xpThresholds"] = lua_table(
            self.h.lua, {20: 200, 21: 300, 22: 400})
        after["heistProtocolProof"]["xpThresholds"] = lua_table(
            self.h.lua, {20: 200, 21: 300, 22: 400})
        if crossing:
            data["reply"]["xp"] = 150
            after["native"]["xp"] = 50
            after["native"]["level"] = 21
            after["native"]["maxLevel"] = 21
        else:
            after["native"]["maxLevel"] = 20
        baseline, reason = self.evidence.capture(data["proposal"], before)
        self.assertIsNone(reason)
        data["baseline"] = baseline
        after["native"]["cash"] += 10000
        after["native"]["pools"]["energy"] = 25
        after["native"]["pools"]["health"] = 90
        after["native"]["pools"]["stamina"] = 50
        after["native"]["derived"] = lua_table(self.h.lua, {
            "attack": 999, "income": 12345})
        return data, after

    def test_exclusive_native_outcome_allows_passive_cash_and_pool_regeneration(self):
        for crossing in (False, True):
            data, after = self.native_regen_case(crossing=crossing)
            with self.subTest(crossing=crossing, kind="saved"):
                self.assertEqual(self.evidence.recoverSaved(data, after), "confirmed")
            after["session"], after["revision"] = "run-a", 8
            thresholds = after["heistProtocolProof"]["xpThresholds"]
            self.protocol_proof(after, 5)
            after["heistProtocolProof"]["xpThresholds"] = thresholds
            with self.subTest(crossing=crossing, kind="live"):
                self.assertEqual(self.evidence.evaluate(data["proposal"],
                    data["before"], after, data["reply"], data["baseline"]),
                    "confirmed")

    def test_regenerated_resources_require_exact_original_native_action_proof(self):
        changes = [
            (("heistProtocolProof", "controllerCounter"), 6),
            (("heistProtocolProof", "nativeJob"), "other"),
            (("heistProtocolProof", "nativeEpoch"), "other"),
            (("heistProtocolProof", "nativeSourceKey"), "b" * 64),
            (("heistBoardProof", "board", "rows", 1, "sabosUsed"), 0),
            (("heistBoardProof", "board", "rows", 1, "sabosUsed"), 2),
            (("heistBoardProof", "board", "favorsLeft"), 12),
            (("sabotageUsageProof", "attempts"), 2),
            (("native", "cash"), 999),
            (("native", "pools", "energy"), 16),
            (("native", "pools", "health"), 79),
            (("native", "pools", "stamina"), 39),
            (("native", "banked"), 201),
            (("native", "respect"), 6),
            (("native", "skillPoints"), 3),
            (("native", "stats", "attack"), 11),
            (("native", "inventory", "restorative"), 1),
            (("native", "inventoryBound", "restorative"), 0),
            (("native", "collection", "w_policebaton"), 0),
            (("native", "collectionBound", "w_policebaton"), 0),
        ]
        for path, value in changes:
            data, after = self.native_regen_case()
            current = after
            for field in path[:-1]:
                current = current[field]
            current[path[-1]] = value
            with self.subTest(path=path, value=value):
                self.assertIsNone(self.evidence.recoverSaved(data, after))
        for reply in (
            {"ok": False}, {"ok": True, "pending": True},
            {"ok": True, "code": "pending"},
            {"ok": True, "code": "no_pending"},
            {"ok": True, "code": "rate_limited"},
            {"ok": True, "code": "presence"},
            {"ok": True, "code": "busy"},
        ):
            data, after = self.native_regen_case()
            data["reply"] = lua_table(self.h.lua, {
                "cash": 0, "xp": 50, **reply})
            with self.subTest(reply=reply):
                self.assertIsNone(self.evidence.recoverSaved(data, after))

    def test_permissive_native_proof_keeps_complete_item_origin_custody(self):
        for field in ("inventory", "inventoryBound", "collection", "collectionBound"):
            for side in ("before", "after"):
                data, after = self.native_regen_case()
                if side == "before":
                    data["before"]["native"][field] = None
                    baseline, reason = self.evidence.capture(data["proposal"],
                        data["before"])
                    self.assertIsNone(reason)
                    data["baseline"] = baseline
                else:
                    after["native"][field] = None
                with self.subTest(field=field, side=side):
                    self.assertIsNone(self.evidence.recoverSaved(data, after))
        data, after = self.native_regen_case()
        after["native"]["inventory"]["restorative"] = 1
        after["native"]["inventoryBound"]["restorative"] = 2
        self.assertIsNone(self.evidence.recoverSaved(data, after))

    def test_permissive_xp_projection_requires_original_and_current_source_quotes(self):
        changes = [
            ("before", ("xpThresholds",), None),
            ("after", ("xpThresholds",), None),
            ("after", ("xpThresholds", 20), 201),
            ("after", ("xpThresholds", 21), 301),
            ("after", ("xpThresholds", 21), None),
        ]
        for side, path, value in changes:
            data, after = self.native_regen_case(crossing=True)
            proof = (data["before"] if side == "before" else after)["heistProtocolProof"]
            current = proof
            for field in path[:-1]:
                current = current[field]
            current[path[-1]] = value
            if side == "before":
                baseline, reason = self.evidence.capture(data["proposal"], data["before"])
                self.assertIsNone(reason)
                data["baseline"] = baseline
            with self.subTest(side=side, path=path):
                self.assertIsNone(self.evidence.recoverSaved(data, after))
        for field, value in (("xp", 51), ("level", 22), ("maxLevel", 20),
                             ("skillPoints", 3)):
            data, after = self.native_regen_case(crossing=True)
            after["native"][field] = value
            with self.subTest(field=field):
                self.assertIsNone(self.evidence.recoverSaved(data, after))
        for xp in (None, -1, 1.5):
            data, after = self.native_regen_case()
            data["reply"]["xp"] = xp
            with self.subTest(reply_xp=xp):
                self.assertIsNone(self.evidence.recoverSaved(data, after))

    def test_passive_resource_fallback_preserves_legacy_and_exact_rejection_rules(self):
        data, after = self.recovery_case()
        after["native"]["cash"] += 10000
        after["native"]["pools"]["energy"] = 25
        self.assertIsNone(self.evidence.recoverSaved(data, after))
        after["session"], after["revision"] = "run-a", 8
        self.assertEqual(self.evidence.evaluate(data["proposal"], data["before"],
            after, data["reply"], data["baseline"]), "confirmed")
        for field, value in (("cash", 1001), ("energy", 25)):
            data, after = self.recovery_case(ok=False, native=True)
            if field == "energy":
                after["native"]["pools"][field] = value
            else:
                after["native"][field] = value
            with self.subTest(rejected_change=field):
                self.assertIsNone(self.evidence.recoverSaved(data, after))


    def test_permissive_native_pools_refuse_unknown_original_numeric_state(self):
        data, after = self.native_regen_case()
        data["before"]["native"]["pools"]["health"] = "unknown"
        baseline, reason = self.evidence.capture(data["proposal"], data["before"])
        self.assertIsNone(reason)
        data["baseline"] = baseline
        try:
            result = self.evidence.recoverSaved(data, after)
        except Exception as error:
            self.fail("Unknown original pool data must remain held: " + str(error))
        self.assertIsNone(result)

    def test_permissive_xp_can_cross_multiple_source_quoted_levels(self):
        data, after = self.native_regen_case(crossing=True)
        data["reply"]["xp"] = 450
        after["native"]["level"], after["native"]["xp"] = 22, 50
        after["native"]["maxLevel"] = 22
        after["heistProtocolProof"]["xpThresholds"] = lua_table(
            self.h.lua, {22: 400})
        self.assertEqual(self.evidence.recoverSaved(data, after), "confirmed")


if __name__ == "__main__":
    unittest.main()
