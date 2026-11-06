"""The tab combines source-bound map/bonus/season/fort facts without a mutation."""
import unittest
from engine_harness import Harness, lua_table


class TerritoryWatchIntegrationTests(unittest.TestCase):
    def test_tab_factories_attachment_and_status_display_are_read_only(self):
        h = Harness()
        paths = {
            "TerritoryMapQuery": "src/tabs/territory/TerritoryMapQuery.luau",
            "ResidencyQuery": "src/tabs/territory/ResidencyQuery.luau",
            "TerritoryState": "src/tabs/territory/TerritoryState.luau",
            "ReadAttachment": "src/tabs/territory/ReadAttachment.luau",
            "TerritoryBlocked": "src/tabs/territory/TerritoryBlocked.luau",
            "TerritoryBonuses": "src/tabs/territory/TerritoryBonuses.luau",
            "FortificationQuery": "src/tabs/territory/FortificationQuery.luau",
            "TerritorySeasonSource": "src/tabs/territory/TerritorySeasonSource.luau"}
        deps = {key: h.load(path) for key, path in paths.items()}
        deps.update(fingerprint="a" * 64, release="release-a")
        season, reason = deps["TerritorySeasonSource"].new(
            h.lua.eval("function() return {season=2, startsAt=900, endsAt=2000} end"),
            h.lua.eval("function(live,now) return {phase='running', n=live.season, startsAt=live.startsAt, endsAt=live.endsAt} end"),
            "a" * 64, "release-a")
        self.assertIsNone(reason)
        deps["territorySeasonSource"] = season
        tab = h.load("src/tabs/territory/Module.luau").new(lua_table(h.lua, deps))
        raw = h.snapshot(native={"fullSync": True, "serverNow": 1000,
            "family": {"id": "fam-a"}, "derived": {"territoryBonusSources": {
                "known": True, "familyId": "fam-a", "kinds": {"landlord": {
                    "total": 0.05, "active": ["d1"], "inactive": []}}}}})
        raw = tab.Enrich(tab, raw)[0]
        query = tab.NewMapQuery(tab)
        request = query.Prepare(query, "vespera", raw)[0]
        mapped, reason = query.Accept(query, request, lua_table(h.lua, {
            "ok": True, "city": "vespera", "territoryCapacity": {"familyId": "fam-a"},
            "districts": [{"id": "d1", "mine": True, "shieldUntil": 1100}]}))
        self.assertIsNone(reason)
        raw = tab.AttachReads(tab, raw, mapped)[0]
        fort = tab.NewFortificationQuery(tab)[0]
        request = fort.Prepare(fort, "d1", raw)[0]
        accepted, reason = fort.Accept(fort, request, lua_table(h.lua, {
            "ok": True, "fort": {"structures": [{"key": key, "lv": 1}
                for key in ("barricade", "guardposts", "clinic", "apartment")]}}))
        self.assertIsNone(reason)
        raw, reason = tab.AttachFortification(tab, raw, accepted)
        self.assertIsNone(reason)
        watch = tab.Descriptors(tab)[1]
        view, reason = watch.reader.read(raw, raw)
        self.assertIsNone(reason)
        self.assertEqual(view.districts[1].shieldRemaining, 100)
        proposal, report = watch.planner.propose(view, lua_table(h.lua, {"enabled": True,
            "showSeason": True, "showFortifications": True}))
        self.assertIsNone(proposal)
        self.assertIn("1/1 held", report)
        self.assertIn("landlord +5%", report)
        self.assertIn("season 2 running", report)
        self.assertIn("barricade L1", report)
        _, report = watch.planner.propose(view, lua_table(h.lua, {"enabled": True,
            "showSeason": False, "showFortifications": False}))
        self.assertNotIn("season", report)
        self.assertNotIn("barricade", report)
        self.assertEqual(len(h.transport.sent), 0)


if __name__ == "__main__": unittest.main()
