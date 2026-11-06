"""Actual Territory tab queries use the shared lease and native attachment."""
import unittest
from engine_harness import lua_table
import test_native_client_bindings as native_fixture


class TerritorySharedSourcesTests(unittest.TestCase):
    def setUp(self):
        self.h, self.game, _, self.remotes, _, _, _, bindings = native_fixture.NativeClientBindingsTests().make_client()
        self.city_source = bindings.currentTerritoryCities
        deps = {name: self.h.load("src/tabs/territory/" + name + ".luau") for name in (
            "TerritoryMapQuery", "ResidencyQuery", "TerritoryState", "ReadAttachment", "TerritoryBlocked",
            "DistrictQuery", "FortificationQuery", "TerritoryBonuses", "TerritoryReadSources")}
        deps.update(fingerprint="a" * 64, release="release-a", territoryCitySource=self.city_source, gameData=bindings.gameData)
        self.tab = self.h.load("src/tabs/territory/Module.luau").new(lua_table(self.h.lua, deps))
        self.reader = self.h.load("src/transport/NativeSnapshotReader.luau").new(
            lua_table(self.h.lua, self.h.session), self.h.clock, "a" * 64)
        self.native = lua_table(self.h.lua, {"serverNow": 1000, "family": {"id": "fam-a"},
            "cityId": "vespera", "derived": {}, "crew": [{"name": "YOU"}]})
        self.reader.ObserveSync(self.reader, self.native)
        self.lane = self.h.load("src/engine/RequestLane.luau").new(self.h.clock)
        self.executor = self.h.lua.execute("""return {calls={},queued={},
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn return true end,
            InvokeOwned=function(self,lease,remote,method,...)
                local args=table.pack(...)
                self.calls[#self.calls+1]={remote=remote,args=args}
                if args[1]=='map' then if self.mapReply then return self.mapReply end; return {ok=true,city='vespera',territoryCapacity={familyId='fam-a'},
                    districts={{id='d1',mine=true,shieldUntil=1100}}} end
                if args[1]=='district' then return {ok=true,district={id=args[2],mine=true,holderId='fam-a',
                    garrisonCount=2,garrisonCap=10,revision=5}} end
                if args[1]=='view' then return {ok=true,districtId=args[2],admission='open',kind='landlord',rent=3} end
                if args[1]=='fortview' then return {ok=true,fort={structures={
                    {key='barricade',lv=1},{key='guardposts',lv=0},{key='clinic',lv=0},{key='apartment',lv=0}}}} end
                error('Unexpected mutation')
            end}""")
        self.sources = self.tab.ReadSources(self.tab, self.reader)
        self.settings = lua_table(self.h.lua, {"territoryWatch": {"enabled": True,
            "custom": {"districtId": "d1", "showFortifications": True}},
            "residency": {"enabled": True, "custom": {"districtId": "d1"}}})
        specs = [{"id": source.id, "interval": source.interval} for source in self.sources.values()]
        self.h.lua.globals().territoryNativeReader = self.reader
        self.coordinator = self.h.load("src/transport/ReadCoordinator.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "lane": self.lane, "executor": self.executor, "sources": self.sources,
            "budget": self.h.load("src/engine/ReadBudget.luau").new(self.h.clock, lua_table(self.h.lua, specs), 5, 60),
            "currentSnapshot": self.h.lua.eval("function() return territoryNativeReader:Capture() end")}))

    def tearDown(self):
        self.coordinator.Close(self.coordinator)
        self.tab.Close(self.tab)
        self.reader.Close(self.reader)

    def step(self, drain=True):
        eligible = self.h.lua.table()
        for source in self.sources.values():
            eligible[source.id] = source.enabled(self.settings, None, self.reader.Capture(self.reader)[0])
        result = self.coordinator.Step(self.coordinator, self.reader.Capture(self.reader)[0], eligible)
        if drain:
            while len(self.executor.queued):
                queued = self.executor.queued
                self.executor.queued = self.h.lua.table()
                for callback in queued.values():
                    callback()
        return result

    def test_district_and_fortification_wait_for_the_matching_map_after_sync(self):
        dependent={source.id:source for source in self.sources.values()
                   if source.id in ('territoryDistrict','fortificationView')}
        def enabled():
            raw=self.reader.Capture(self.reader)[0]
            return {name:source.enabled(self.settings,None,raw) for name,source in dependent.items()}
        self.assertEqual(enabled(),{'territoryDistrict':False,'fortificationView':False})
        self.step()
        self.assertEqual(enabled(),{'territoryDistrict':True,'fortificationView':True})
        self.reader.ObserveSync(self.reader,self.native)
        self.assertEqual(enabled(),{'territoryDistrict':False,'fortificationView':False})

    def test_station_display_city_is_resolved_to_native_map_id_before_district_read(self):
        self.settings = lua_table(self.h.lua, {"station": {"enabled": True, "districtId": "d_jade"}})
        self.executor.mapReply = lua_table(self.h.lua, {"ok": True, "city": "jade_harbor",
            "territoryCapacity": {"familyId": "fam-a"}, "districts": [{"id": "d_jade", "mine": True}]})
        for index in range(3):
            self.h.at(index * .1)
            self.step()
        self.assertEqual(self.executor.calls[1].args[2], "jade_harbor")
        self.assertEqual(self.executor.calls[1].args.n, 4)
        self.assertIsNone(self.executor.calls[1].args[3])
        self.assertIsNone(self.executor.calls[1].args[4])
        raw = self.reader.Capture(self.reader)[0]
        self.assertEqual(raw.territoryMap.cityId, "jade_harbor")
        self.assertEqual(raw.territoryDistrict.district.id, "d_jade")

    def test_missing_station_city_mapping_schedules_no_guessed_map(self):
        self.settings = lua_table(self.h.lua, {"station": {"enabled": True, "districtId": "d_jade"}})
        self.remotes.Parent.children.CityMaps.Value.BY_NAME["Jade Harbor"] = None
        self.step()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertIsNone(self.reader.Capture(self.reader)[0].territoryMap)

    def test_replaced_city_source_rejects_queued_map_reply_and_clears_current_map(self):
        self.step(False)
        self.remotes.Parent.children.CityMaps.Value.BY_NAME = self.h.lua.table()
        self.executor.queued[1]()
        self.assertIsNone(self.reader.Capture(self.reader)[0].territoryMap)
        self.h.at(.1)
        self.step()
        self.assertIsNone(self.reader.Capture(self.reader)[0].territoryMap)

    def test_disabled_native_city_maps_keep_explicit_nil_in_source_query(self):
        self.remotes.Parent.children.Config.Value.TERRITORY.cityMaps = False
        source = self.h.load("src/transport/NativeClientBindings.luau").read(
            self.game, self.h.lua.eval("function(module) return module.Value end"))[0].currentTerritoryCities
        deps = self.tab.deps
        deps.territoryCitySource = source
        owner = self.h.load("src/tabs/territory/TerritoryReadSources.luau").new(deps)
        sources = owner.Sources(owner, self.reader)
        map_source = next(value for value in sources.values() if value.id == "territoryMap")
        raw = self.reader.Capture(self.reader)[0]
        self.settings.territoryWatch.custom.cityId = "jade_harbor"
        self.assertTrue(map_source.enabled(self.settings, None, raw))
        request, why = map_source.prepare(raw)
        self.assertIsNone(why)
        self.assertEqual(request.arity, 4)
        self.assertIsNone(request.args[2])
        self.assertIsNone(request.args[3])
        self.assertIsNone(request.args[4])
        owner.Close(owner)

    def test_missing_bound_city_source_schedules_no_station_map(self):
        self.settings = lua_table(self.h.lua, {"station": {"enabled": True, "districtId": "d_jade"}})
        self.tab.deps.territoryCitySource = None
        self.step()
        self.assertEqual(len(self.executor.calls), 0)

    def test_replaced_city_source_clears_previously_accepted_map_and_district(self):
        for index in range(4):
            self.h.at(index * .1)
            self.step()
        self.assertIsNotNone(self.reader.Capture(self.reader)[0].territoryMap)
        self.assertIsNotNone(self.reader.Capture(self.reader)[0].territoryDistrict)
        self.remotes.Parent.children.CityMaps.Parent = None
        self.h.at(.5)
        self.step()
        raw = self.reader.Capture(self.reader)[0]
        self.assertIsNone(raw.territoryMap)
        self.assertIsNone(raw.territoryDistrict)

    def test_actual_app_default_map_uses_last_native_unlocked_city(self):
        self.native.level = 40
        self.reader.ObserveSync(self.reader, self.native)
        self.executor.mapReply = lua_table(self.h.lua, {"ok": True, "city": "jade_harbor",
            "territoryCapacity": {"familyId": "fam-a"}, "districts": [{"id": "d_jade", "mine": True}]})
        app, runtime = self.start_app()
        try:
            app.Set(app, "territoryWatch.enabled", True)
            app.Resume(app)
            app.Step(app, self.reader.Capture(self.reader)[0])
            self.executor.queued[1]()
            self.assertEqual(self.executor.calls[1].args[2], "jade_harbor")
            self.assertEqual(self.reader.Capture(self.reader)[0].territoryMap.cityId, "jade_harbor")
        finally:
            app.Destroy(app)

    def test_all_four_reads_attach_to_origin_and_issue_no_mutation(self):
        for index in range(8):
            self.h.at(index * .1)
            self.step()
        raw = self.reader.Capture(self.reader)[0]
        self.assertEqual(raw.territoryMap.cityId, "vespera")
        self.assertEqual(raw.territoryDistrict.district.garrisonCount, 2)
        self.assertEqual(raw.residencyView.districtId, "d1")
        self.assertEqual(raw.fortificationView.fort.structures[1].lv, 1)
        self.assertEqual({call.args[1] for call in self.executor.calls.values()}, {"map", "district", "view", "fortview"})
        call = next(row for row in self.executor.calls.values() if row.args[1] == "district")
        self.assertEqual(call.args.n, 4)
        self.assertIsNone(call.args[4])

    def test_all_off_does_not_schedule_and_changed_sync_drops_queued_read(self):
        self.settings = self.h.lua.table()
        self.step()
        self.assertEqual(len(self.executor.calls), 0)
        self.settings.territoryWatch = lua_table(self.h.lua, {"enabled": True})
        self.step(False)
        self.reader.ObserveSync(self.reader, self.native)
        self.executor.queued[1]()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertIsNone(self.reader.Capture(self.reader)[0].territoryMap)

    def test_new_sync_invalidates_all_accepted_territory_reads(self):
        for index in range(5):
            self.h.at(index * .1)
            self.step()
        self.reader.ObserveSync(self.reader, self.native)
        raw = self.reader.Capture(self.reader)[0]
        for field in ("territoryMap", "territoryDistrict", "residencyView", "fortificationView"):
            self.assertIsNone(raw[field])

    def test_shared_mutation_owner_prevents_background_reads(self):
        self.assertIsNotNone(self.lane.TryAcquire(self.lane, "mutation", "busy", 45))
        self.step()
        self.assertEqual(len(self.executor.calls), 0)
        self.assertEqual(len(self.executor.queued), 0)

    def test_native_attachment_rejects_wrong_source_and_family_without_aliasing(self):
        self.step()
        raw = self.reader.Capture(self.reader)[0]
        staged = self.h.lua.table()
        for name in ("session", "account", "place", "release", "revision", "capturedAt", "native"):
            staged[name] = raw[name]
        staged.territoryRead = lua_table(self.h.lua, {"sourceKey": "b" * 64, "field": "territoryMap"})
        staged.territoryRead.value = raw.territoryMap
        self.assertFalse(self.reader.AttachTerritoryRead(self.reader, staged))
        staged.territoryRead.sourceKey = "a" * 64
        raw.territoryMap.territoryCapacity.familyId = "other"
        self.assertFalse(self.reader.AttachTerritoryRead(self.reader, staged))
        self.assertEqual(self.reader.Capture(self.reader)[0].territoryMap.territoryCapacity.familyId, "fam-a")

    def test_changed_selection_discards_old_reply_and_close_fences_queued_calls(self):
        self.step(False)
        self.settings.territoryWatch.custom.cityId = "exiles"
        # Read-only selection changes cannot attach a result for the old choice.
        self.executor.queued[1]()
        self.assertIsNone(self.reader.Capture(self.reader)[0].territoryMap)
        self.h.at(.1)
        self.step(False)
        before = len(self.executor.calls)
        self.coordinator.Close(self.coordinator)
        for callback in self.executor.queued.values():
            callback()
        self.assertEqual(len(self.executor.calls), before)

    def start_app(self):
        modules = {name: self.h.load("src/engine/" + name + ".luau") for name in (
            "Contracts", "Broker", "Journal", "Session", "Scheduler", "ResourceReservations")}
        modules["Checkpoint"] = self.h.load("src/storage/Checkpoint.luau")
        modules["Context"] = self.h.load("src/game/Context.luau")
        watch = self.tab.Descriptors(self.tab)[1]
        runtime = self.h.load("src/engine/AutomationRuntime.luau").new(lua_table(self.h.lua, {
            "clock": self.h.clock, "transport": self.h.transport, "identity": self.h.session, "modules": modules,
            "storage": self.h.lua.execute("return {strictRecovery=true,Read=function() end,Write=function() return true end}"),
            "features": [watch], "tabInstances": [self.tab], "readCoordinator": self.coordinator, "readSources": self.sources,
            "featurePages": {'territoryWatch': 'territory'},
            "snapshotAssembler": self.h.load('src/tabs/TabSnapshotAssembler.luau').new(lua_table(self.h.lua, [self.tab]))}))
        app = self.h.load("src/App.luau").start(lua_table(self.h.lua, {
            "Ember": self.h.load("tests/ember_double.lua")(), "Catalog": self.h.load("src/ui/Catalog.luau"),
            "Settings": self.h.load("src/storage/Settings.luau"), "EmberAdapter": self.h.load("src/ui/EmberAdapter.luau"),
            "TerritoryTab": self.h.load("src/tabs/territory/Module.luau"), "automationRuntimeInstance": runtime}))
        return app,runtime

    def test_app_reports_current_holdings_and_user_fortification_display_choice(self):
        self.native.derived.territoryBonusSources = lua_table(self.h.lua, {
            'known': True,'familyId': 'fam-a','kinds': {
                'crateLuck': {'total': .25,'active': ['d1'],'inactive': []}}})
        self.reader.ObserveSync(self.reader, self.native)
        self.tab.season = self.h.load('src/tabs/territory/TerritorySeasonSource.luau').new(
            self.h.lua.eval('function() return {season=2,startsAt=900,endsAt=2000} end'),
            self.h.lua.eval('function(live,now) return {phase="running",n=live.season,startsAt=live.startsAt,endsAt=live.endsAt} end'),
            'a' * 64, 'release-a')[0]
        app,runtime = self.start_app()
        app.Set(app, "territoryWatch.enabled", True)
        app.Set(app, "territoryWatch.custom.districtId", "d1")
        app.Set(app, "territoryWatch.custom.showFortifications", True)
        app.Resume(app)
        try:
            for index in range(5):
                self.h.at(index * .1)
                app.Step(app, self.reader.Capture(self.reader)[0])
                while len(self.executor.queued):
                    queued, self.executor.queued = self.executor.queued, self.h.lua.table()
                    for callback in queued.values():
                        callback()
            status = runtime.Status(runtime)
            self.assertIn("1/1 held", status.reasons.territoryWatch)
            self.assertIn("barricade L1", status.reasons.territoryWatch)
            self.assertIn('crateLuck +25%', status.reasons.territoryWatch)
            self.assertIn('season 2 running', status.reasons.territoryWatch)
            self.assertIn('d1 garrison 2/10', status.reasons.territoryWatch)
            self.assertIn('shield observed 100s', status.reasons.territoryWatch)
            app.Set(app, "territoryWatch.custom.showFortifications", False)
            app.Set(app, 'territoryWatch.custom.showSeason', False)
            self.h.at(.6)
            app.Step(app, self.reader.Capture(self.reader)[0])
            self.assertNotIn("barricade", runtime.Status(runtime).reasons.territoryWatch)
            self.assertNotIn('season 2', runtime.Status(runtime).reasons.territoryWatch)
            app.Set(app, 'territoryWatch.custom.districtId', 'd2')
            self.h.at(.7)
            app.Step(app, self.reader.Capture(self.reader)[0])
            self.assertNotIn('d1 garrison', runtime.Status(runtime).reasons.territoryWatch)
            self.assertNotIn('shield observed', runtime.Status(runtime).reasons.territoryWatch)
            self.assertEqual(len(self.h.transport.sent), 0)
        finally:
            app.Destroy(app)
            self.assertIsNone(self.tab.season.Enrich(self.tab.season,
                self.reader.Capture(self.reader)[0])[0])
