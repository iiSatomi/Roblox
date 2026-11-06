"""Native SeasonLive/status callbacks supply a stamped display, never a calendar copy."""
import unittest

from engine_harness import Harness, ROOT, lua_table


class TerritorySeasonSourceTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        path = ROOT / "src/tabs/territory/TerritorySeasonSource.luau"
        self.assertTrue(path.is_file(), "Missing TerritorySeasonSource")
        self.module = self.h.load(path.relative_to(ROOT).as_posix())
        self.callbacks = self.h.lua.execute("""return {
            live={season=1,startsAt=900,endsAt=2000},
            result={phase='running',n=1,startsAt=900,endsAt=2000}, calls=0
        }""")
        self.h.lua.globals().seasonCallbacks = self.callbacks
        self.read_live = self.h.lua.eval("function() return seasonCallbacks.live end")
        self.status = self.h.lua.eval("""function(live, now)
            seasonCallbacks.calls=seasonCallbacks.calls+1
            seasonCallbacks.seenLive=live; seasonCallbacks.seenNow=now
            return seasonCallbacks.result
        end""")
        self.source, reason = self.module.new(self.read_live, self.status, "a" * 64, "release-a")
        self.assertIsNone(reason)

    def raw(self, revision=1, server=1000):
        return self.h.snapshot(revision=revision, captured_at=10,
            native={"fullSync": True, "serverNow": server})

    def test_native_running_status_uses_native_time_and_detached_stamped_facts(self):
        raw = self.raw()
        enriched, reason = self.source.Enrich(self.source, raw)
        self.assertIsNone(reason)
        self.assertIsNone(raw.territorySeason)
        self.assertEqual(self.callbacks.seenNow, 1000)
        self.assertEqual(self.callbacks.seenLive.season, 1)
        self.assertEqual(enriched.territorySeason.remaining, 1000)
        self.callbacks.result.endsAt = 99999
        self.callbacks.live.season = 99
        self.assertEqual(enriched.territorySeason.endsAt, 2000)
        view, reason = self.source.Read(self.source, enriched, raw)
        self.assertIsNone(reason)
        self.assertTrue(view.readOnly)
        self.assertEqual(view.phase, "running")
        view.header.revision = 9
        self.assertEqual(enriched.territorySeason.header.revision, 1)
        self.assertEqual(len(self.h.transport.sent), 0)

    def test_upcoming_and_pre_preserve_native_phases_without_invented_deadlines(self):
        self.callbacks.live = lua_table(self.h.lua, {"season": 0, "closed": True})
        self.callbacks.result = lua_table(self.h.lua, {"phase": "upcoming", "n": 1, "startsAt": 1500})
        upcoming = self.source.Enrich(self.source, self.raw())[0].territorySeason
        self.assertEqual((upcoming.phase, upcoming.n, upcoming.remaining), ("upcoming", 1, 500))
        self.assertIsNone(upcoming.endsAt)
        self.callbacks.result = lua_table(self.h.lua, {"phase": "pre", "n": 2})
        pre = self.source.Enrich(self.source, self.raw())[0].territorySeason
        self.assertEqual(pre.phase, "pre")
        self.assertIsNone(pre.startsAt)
        self.assertIsNone(pre.endsAt)
        self.assertIsNone(pre.remaining)

    def test_invalid_live_status_and_callback_errors_are_unavailable(self):
        self.callbacks.live = "malformed decoded attribute"
        self.assertIsNone(self.source.Enrich(self.source, self.raw())[0])
        self.assertEqual(self.callbacks.calls, 0)
        self.callbacks.live = lua_table(self.h.lua, {"season": 1})
        for result in (None, {"phase": "unknown", "n": 1}, {"phase": "running", "n": 1},
                {"phase": "running", "n": 1, "startsAt": 2000, "endsAt": 900},
                {"phase": "upcoming", "n": 1, "startsAt": float("inf")},
                {"phase": "pre", "n": 0}, {"phase": "pre", "n": 2, "startsAt": 1500}):
            self.callbacks.result = lua_table(self.h.lua, result)
            self.assertIsNone(self.source.Enrich(self.source, self.raw())[0], result)
        broken = self.h.lua.eval("function() error('not available') end")
        for read_live, status in ((broken, self.status), (self.read_live, broken)):
            source = self.module.new(read_live, status, "a" * 64, "release-a")[0]
            self.assertIsNone(source.Enrich(source, self.raw())[0])

    def test_successful_nil_attribute_delegates_native_calendar_fallback(self):
        self.callbacks.live = None
        enriched, reason = self.source.Enrich(self.source, self.raw())
        self.assertIsNone(reason)
        self.assertEqual(self.callbacks.calls, 1)
        self.assertIsNone(self.callbacks.seenLive)
        self.assertEqual(self.callbacks.seenNow, 1000)
        self.assertTrue(enriched.territorySeason.calendarFallback)
        view, reason = self.source.Read(self.source, enriched, self.raw())
        self.assertIsNone(reason)
        self.assertTrue(view.calendarFallback)
        self.callbacks.live = lua_table(self.h.lua, {"season": 1})
        live = self.source.Enrich(self.source, self.raw())[0].territorySeason
        self.assertFalse(live.calendarFallback)

    def test_full_sync_version_source_key_revision_and_server_time_fences(self):
        raw = self.raw()
        enriched = self.source.Enrich(self.source, raw)[0]
        for field, value in (("revision", 2), ("session", "other"), ("release", "new")):
            current = self.raw()
            current[field] = value
            current.territorySeason = enriched.territorySeason
            self.assertIsNone(self.source.Read(self.source, current, current)[0])
        current = self.raw(server=1001)
        current.territorySeason = enriched.territorySeason
        self.assertIsNone(self.source.Read(self.source, current, current)[0])
        enriched.territorySeason.sourceKey = "b" * 64
        self.assertIsNone(self.source.Read(self.source, enriched, raw)[0])
        raw.native.fullSync = False
        self.assertIsNone(self.source.Enrich(self.source, raw)[0])
        raw = self.raw()
        raw.release = "other"
        self.assertIsNone(self.source.Enrich(self.source, raw)[0])

    def test_mutated_snapshot_during_callback_and_closed_source_do_not_stamp_stale_data(self):
        raw = self.raw()
        self.h.lua.globals().seasonRaw = raw
        mutate = self.h.lua.eval("function() seasonRaw.revision=2; return seasonCallbacks.live end")
        source = self.module.new(mutate, self.status, "a" * 64, "release-a")[0]
        self.assertIsNone(source.Enrich(source, raw)[0])
        self.source.Close(self.source)
        self.assertIsNone(self.source.Enrich(self.source, self.raw())[0])

    def test_constructor_and_live_fields_are_strictly_bounded(self):
        self.assertIsNone(self.module.new(None, self.status, "a" * 64, "release-a")[0])
        self.assertIsNone(self.module.new(self.read_live, self.status, "bad", "release-a")[0])
        for live in ("{bad json}", {}, {"season": -1}, {"season": 1, "closed": "false"},
                     {"season": 1, "endsAt": float("nan")}):
            self.callbacks.live = lua_table(self.h.lua, live)
            self.assertIsNone(self.source.Enrich(self.source, self.raw())[0])

    def test_new_capture_invalidates_previous_generation_even_for_same_sync(self):
        previous = self.source.Enrich(self.source, self.raw())[0]
        self.callbacks.result = lua_table(self.h.lua, {"phase": "upcoming", "n": 2, "startsAt": 1800})
        latest = self.source.Enrich(self.source, self.raw())[0]
        self.assertIsNone(self.source.Read(self.source, previous, self.raw())[0])
        self.assertEqual(self.source.Read(self.source, latest, self.raw())[0].phase, "upcoming")

    def test_plausible_forged_display_cannot_replace_this_capture(self):
        enriched = self.source.Enrich(self.source, self.raw())[0]
        enriched.territorySeason.n = 99
        self.assertIsNone(self.source.Read(self.source, enriched, self.raw())[0])


if __name__ == "__main__":
    unittest.main()
