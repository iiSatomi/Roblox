"""Native owner and resource arbitration without game calls."""
from pathlib import Path
import unittest

from lupa import LuaRuntime

from engine_harness import ROOT, lua_table


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        for path in ("src/game/Context.luau", "src/engine/Scheduler.luau"):
            self.assertTrue((ROOT / path).is_file(), f"{path} missing")
        contracts = self.lua.execute(
            (ROOT / "src/engine/Contracts.luau").read_text(encoding="utf-8")
        )
        self.context = self.lua.execute(
            (ROOT / "src/game/Context.luau").read_text(encoding="utf-8")
        ).new(contracts)
        self.scheduler = self.lua.execute(
            (ROOT / "src/engine/Scheduler.luau").read_text(encoding="utf-8")
        ).new()
        self.session = {
            "session": "run-a", "account": "user-a", "place": "73897506680154",
            "release": "release-a",
        }

    def read(self, native=None, captured_at=0, now=0, **changes):
        raw = {
            **self.session, "revision": 1, "capturedAt": captured_at,
            "native": native if native is not None else {
                "fullSync": True, "level": 2, "cash": 100,
                "pools": {"energy": 5}, "derived": {"autoJobs": False},
                "serverNow": 12345,
            },
        }
        raw.update(changes)
        return self.context.Read(
            self.context, lua_table(self.lua, raw), lua_table(self.lua, self.session), now, 2
        )

    def proposal(self, feature, key, energy=1):
        return lua_table(self.lua, {
            **self.session, "revision": 1, "feature": feature,
            "actionKey": key, "resources": {"energy": energy},
            "intent": {"kind": feature, "targetId": key},
        })

    def desired(self, proposals, enabled=None, reservations=None, uncertain=None):
        return lua_table(self.lua, {
            "proposals": proposals,
            "enabled": enabled or {p["feature"]: True for p in proposals},
            "reservations": reservations or {}, "uncertain": uncertain or {},
        })

    def test_context_separates_entitlement_from_activity(self):
        active = {
            "fullSync": True, "level": 2, "cash": 100,
            "pools": {"energy": 5}, "derived": {"autoJobs": True},
            "autoJob": {"mode": "one", "jobId": "j_watch"},
        }
        view, reason = self.read(active)
        self.assertIsNone(reason)
        self.assertTrue(view["owners"]["jobs"]["entitled"])
        self.assertEqual(view["owners"]["jobs"]["activity"], "active")
        inactive, _ = self.read({**active, "autoJob": None})
        self.assertEqual(inactive["owners"]["jobs"]["activity"], "inactive")
        unknown, _ = self.read({**active, "fullSync": False, "autoJob": None})
        self.assertEqual(unknown["owners"]["jobs"]["activity"], "unknown")
        partial_active, _ = self.read({**active, "fullSync": False})
        self.assertEqual(partial_active["owners"]["jobs"]["activity"], "unknown")

    def test_other_native_controller_owners_use_their_own_saved_state(self):
        native = {
            "fullSync": True, "pools": {"energy": 5},
            "derived": {"autoBuy": False, "autoRoll": True, "autoBoss": False},
            "autoBuyRules": {"on": True},
            "autoRolls": {"1": {"tier": "silver", "target": 3}},
            "bossStage": {"auto": 4},
        }
        view, reason = self.read(native)
        self.assertIsNone(reason)
        self.assertFalse(view["owners"]["shop"]["entitled"])
        self.assertEqual(view["owners"]["shop"]["activity"], "active")
        self.assertTrue(view["owners"]["crewRoll"]["entitled"])
        self.assertEqual(view["owners"]["crewRoll"]["activity"], "active")
        self.assertEqual(view["owners"]["bosses"]["activity"], "active")

        native["autoBuyRules"]["on"] = False
        native["autoRolls"] = {}
        native["bossStage"]["auto"] = None
        inactive, _ = self.read(native)
        for feature in ("shop", "crewRoll", "bosses"):
            self.assertEqual(inactive["owners"][feature]["activity"], "inactive")

        native["autoBuyRules"]["on"] = "yes"
        native["autoRolls"] = {"1": "bad"}
        native["bossStage"] = {}
        unknown, _ = self.read(native)
        self.assertEqual(unknown["owners"]["shop"]["activity"], "unknown")
        self.assertEqual(unknown["owners"]["crewRoll"]["activity"], "unknown")
        self.assertEqual(unknown["owners"]["bosses"]["activity"], "inactive")
        partial, _ = self.read({**native, "fullSync": False})
        for feature in ("shop", "crewRoll", "bosses"):
            self.assertEqual(partial["owners"][feature]["activity"], "unknown")

    def test_scheduler_yields_only_active_native_domain(self):
        native = {
            "fullSync": True, "pools": {"energy": 5},
            "autoBuyRules": {"on": True}, "autoRolls": {},
            "bossStage": {"auto": None},
        }
        context, _ = self.read(native)
        shop = self.proposal("shop", "shop:1")
        jobs = self.proposal("jobs", "job:1")
        chosen, reason = self.scheduler.Choose(
            self.scheduler, context, self.desired([shop, jobs]),
            lua_table(self.lua, {"nextSendAt": 0}), 0,
        )
        self.assertIsNone(reason)
        self.assertEqual(chosen["feature"], "jobs")
        for feature, native_state in (
            ("crewRoll", {"autoRolls": {"1": {"tier": "silver"}}}),
            ("bosses", {"bossStage": {"auto": 4}}),
        ):
            other = {"fullSync": True, "pools": {"energy": 5}, **native_state}
            view, _ = self.read(other)
            chosen, reason = self.scheduler.Choose(
                self.scheduler, view,
                self.desired([self.proposal(feature, feature + ":1"), jobs]),
                lua_table(self.lua, {"nextSendAt": 0}), 0,
            )
            self.assertIsNone(reason)
            self.assertEqual(chosen["feature"], "jobs")

    def test_context_rejects_stale_or_wrong_account(self):
        stale, reason = self.read(captured_at=0, now=3)
        self.assertIsNone(stale)
        self.assertIn("stale", reason.lower())
        wrong, reason = self.read(account="other")
        self.assertIsNone(wrong)
        self.assertIn("account", reason)

    def test_active_or_unknown_native_jobs_yields_to_other_work(self):
        jobs = self.proposal("jobs", "job:1")
        property_action = self.proposal("properties", "property:1")
        desired = self.desired([jobs, property_action])
        for full_sync, expected in ((True, "active"), (False, "unknown")):
            native = {"fullSync": full_sync, "pools": {"energy": 5},
                      "autoJob": {"mode": "one"} if full_sync else None}
            context, _ = self.read(native)
            self.assertEqual(context["owners"]["jobs"]["activity"], expected)
            chosen, reason = self.scheduler.Choose(self.scheduler, context, desired,
                                                   lua_table(self.lua, {"nextSendAt": 0}), 0)
            self.assertIsNone(reason)
            self.assertEqual(chosen["feature"], "properties")

    def test_priority_and_waiting_high_priority_do_not_starve_others(self):
        context, _ = self.read()
        actions = [self.proposal("jobs", "job:1"),
                   self.proposal("operations", "operation:1"),
                   self.proposal("favors", "favor:1"),
                   self.proposal("heists", "heist:1")]
        status = lua_table(self.lua, {"nextSendAt": 0})
        chosen, _ = self.scheduler.Choose(self.scheduler, context,
                                          self.desired(actions), status, 0)
        self.assertEqual(chosen["feature"], "heists")
        waiting = self.desired(actions, reservations={"energy": 5})
        chosen, reason = self.scheduler.Choose(self.scheduler, context, waiting, status, 0)
        self.assertIsNone(chosen)
        self.assertIn("resource", reason.lower())
        ready = self.desired([self.proposal("jobs", "job:2"),
                              self.proposal("heists", "heist:too-expensive", energy=6)])
        chosen, _ = self.scheduler.Choose(self.scheduler, context, ready, status, 0)
        self.assertEqual(chosen["feature"], "jobs")

    def test_uncertain_resource_exposure_and_broker_owner_block(self):
        context, _ = self.read()
        actions = [self.proposal("jobs", "job:1", energy=4)]
        desired = self.desired(actions, uncertain={"energy": 2})
        chosen, reason = self.scheduler.Choose(
            self.scheduler, context, desired, lua_table(self.lua, {"nextSendAt": 0}), 0
        )
        self.assertIsNone(chosen)
        self.assertIn("resource", reason.lower())
        chosen, reason = self.scheduler.Choose(
            self.scheduler, context, self.desired(actions),
            lua_table(self.lua, {"active": {"feature": "operations"}, "nextSendAt": 0}), 0
        )
        self.assertIsNone(chosen)
        self.assertIn("busy", reason.lower())

    def test_equal_priority_candidates_rotate_without_changing_strict_priority(self):
        context, _ = self.read()
        actions = [self.proposal("jobs", "a-job"),
                   self.proposal("properties", "b-property")]
        desired = self.desired(actions)
        status = lua_table(self.lua, {"nextSendAt": 0})
        first, _ = self.scheduler.Choose(self.scheduler, context, desired, status, 0)
        second, _ = self.scheduler.Choose(self.scheduler, context, desired, status, 0)
        third, _ = self.scheduler.Choose(self.scheduler, context, desired, status, 0)
        self.assertEqual([first["actionKey"], second["actionKey"], third["actionKey"]],
                         ["a-job", "b-property", "a-job"])


if __name__ == "__main__":
    unittest.main()
