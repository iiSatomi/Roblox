"""Native district display cities must resolve through the reviewed CityMaps catalog."""
import unittest

from engine_harness import Harness, lua_table


class TerritoryCityBindingTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.city_maps = lua_table(self.h.lua, {"BY_NAME": {"Jade Harbor": {"id": "jade_harbor", "name": "Jade Harbor"}},
            "BY_ID": {"jade_harbor": {"id": "jade_harbor", "name": "Jade Harbor"}}})
        self.data = lua_table(self.h.lua, {"DISTRICTS_BY_ID": {"d1": {"city": "Jade Harbor"}}})
        self.config = lua_table(self.h.lua, {"TERRITORY": {"garrisonCap": 200}})

    def test_station_catalog_uses_native_request_city_id(self):
        station = self.h.load("src/tabs/territory/Stationing.luau").new(self.config, self.data,
            "a" * 64, "release-a", self.city_maps)
        raw, reason = station.Enrich(station, self.h.snapshot(native={"fullSync": True}))
        self.assertIsNone(reason)
        self.assertEqual(raw.stationCatalogProof.cities.d1, "jade_harbor")

    def test_station_only_map_read_resolves_city_without_slugging_display_name(self):
        deps = lua_table(self.h.lua, {"fingerprint": "a" * 64, "release": "release-a",
            "gameData": self.data, "cityMaps": self.city_maps,
            "TerritoryMapQuery": self.h.load("src/tabs/territory/TerritoryMapQuery.luau"),
            "ResidencyQuery": self.h.load("src/tabs/territory/ResidencyQuery.luau")})
        reader = self.h.lua.execute("return {AttachTerritoryRead=function() return true end, ClearTerritoryRead=function() end}")
        owner = self.h.load("src/tabs/territory/TerritoryReadSources.luau").new(deps)
        source = owner.Sources(owner, reader)[1]
        self.assertTrue(source.enabled(lua_table(self.h.lua, {"station": {"enabled": True, "custom": {"districtId": "d1"}}})))
        call, reason = source.prepare(self.h.snapshot(native={"fullSync": True, "family": {"id": "fam"}}))
        self.assertIsNone(reason)
        self.assertEqual(call.args[2], "jade_harbor")


if __name__ == "__main__":
    unittest.main()
