"""Reviewed GameData city boundaries and Config's named Gold rule."""
import unittest,json
from engine_harness import Harness,ROOT,lua_table
class TrophyTargetCatalogTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.module=self.h.load("src/tabs/trophies/NativeTrophyCatalog.luau")
        self.cities=["ashport","caldera","volkovsk","jade","sterling","veilmont","vespera","exiles"]
        self.ids=["t_ashportkey","t_calderaanchor","t_volkovskbell","t_jadeseal","t_charterseal","t_gildedledger","t_eldersignet","t_grudgeledger"]
        self.data={"ITEMS":[{"id":id,"kind":"trophy"} for id in self.ids+["t_brasskeys","t_deedbook"]],"TROPHY_TRADE_INS":{},
            "CITIES":[{"id":"city_"+city,"firstTier":tier} for city,tier in zip(self.cities,[1,4,6,8,10,12,14,16])],
            "JOBS":json.loads((ROOT/"tests/fixtures/jobs-0.26.530.json").read_text(encoding="utf-8"))["jobs"],
            "PROPERTIES":[{"id":"p_a"},{"id":"p_b"},{"id":"p_other"}],
            "CITY_PROPERTIES":{"city_ashport":["p_a","p_b"]}}
        self.config={"MASTERY":[{"name":"Bronze","completions":25},{"name":"Silver","completions":50},{"name":"Gold","completions":100}]}
    def source(self,data=None,config=None):
        return self.module.new(lua_table(self.h.lua,data or self.data),"a"*64,"release-a",lua_table(self.h.lua,config or self.config),self.h.load("src/tabs/jobs/NativeJobCatalog.luau"))
    def goals(self,source):
        raw=source.Enrich(source,self.h.snapshot(native={"fullSync":True}))[0]
        return {row.id:row.goal for row in raw.trophyCatalog.values()}
    def test_all_102_saved_jobs_partition_into_the_eight_reviewed_city_targets(self):
        goals=self.goals(self.source());seen=set()
        for id,city,count in zip(self.ids,self.cities,[18,12,12,12,12,12,12,12]):
            goal=goals[id];ids=set(goal.ids.values())
            self.assertEqual(goal.cityId,"city_"+city);self.assertEqual(goal.goldTier,3)
            self.assertEqual(len(ids),count);self.assertFalse(seen.intersection(ids));seen.update(ids)
        self.assertEqual(seen,{row["id"] for row in self.data["JOBS"]})
    def test_gold_rank_comes_from_named_rule_not_a_fixed_tier(self):
        goals=self.goals(self.source(config={"MASTERY":[{"name":"Bronze","completions":25},{"name":"Gold","completions":75}]}))
        self.assertEqual(goals["t_ashportkey"].goldTier,2)
    def test_ambiguous_or_missing_gold_disables_mastery_but_preserves_property_metadata(self):
        for rules in ([{"name":"Bronze","completions":25}],
                      [{"name":"Gold","completions":25},{"name":"Gold","completions":100}]):
            goals=self.goals(self.source(config={"MASTERY":rules}))
            self.assertIsNone(goals["t_ashportkey"]);self.assertIsNotNone(goals["t_brasskeys"])
    def test_ambiguous_city_boundary_withholds_mastery_targets(self):
        self.data["CITIES"][1]["firstTier"]=1
        self.assertIsNone(self.goals(self.source())["t_ashportkey"])
    def test_city_properties_use_exact_native_membership_and_return_independent_copies(self):
        data=lua_table(self.h.lua,self.data);source=self.module.new(data,"a"*64,"release-a",lua_table(self.h.lua,self.config),self.h.load("src/tabs/jobs/NativeJobCatalog.luau"))
        goals=self.goals(source)
        self.assertEqual(list(goals["t_brasskeys"].ids.values()),["p_a","p_b"])
        goals["t_brasskeys"].ids[1]="changed";data.CITY_PROPERTIES.city_ashport[1]="p_other"
        self.assertEqual(self.goals(source)["t_brasskeys"].ids[1],"p_a")
    def test_unknown_city_property_does_not_become_an_authorized_target(self):
        self.data["CITY_PROPERTIES"]["city_ashport"].append("unknown")
        goals=self.goals(self.source());self.assertIsNone(goals["t_brasskeys"])
        self.assertIsNotNone(goals["t_deedbook"])
if __name__=="__main__":unittest.main()
