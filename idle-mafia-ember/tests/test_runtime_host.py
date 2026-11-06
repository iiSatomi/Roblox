"""Opt-in host owns subscriptions, timer and App shutdown together."""
import unittest

from engine_harness import Harness, lua_table


class RuntimeHostTests(unittest.TestCase):
    def setUp(self):
        self.h = getattr(self, "provided_h", None) or Harness()
        self.host_module = self.h.load(
            "src/transport/RuntimeHost.luau")
        self.events = self.h.lua.execute("""return {
            sync = nil, changed = nil, disconnected = 0,
            SubscribeSync = function(self, callback)
                self.sync = callback
                return { Disconnect = function()
                    self.disconnected = self.disconnected + 1
                    self.sync = nil
                end }
            end,
            SubscribeChanged = function(self, callback)
                self.changed = callback
                return { Disconnect = function()
                    self.disconnected = self.disconnected + 1
                    self.changed = nil
                end }
            end,
        }""")
        self.h.lua.globals().test_events = self.events
        self.timer = self.h.lua.execute("""return {
            callback = nil, cancelled = false,
            After = function(self, _, callback)
                self.callback = callback
                return 1
            end,
            Cancel = function(self)
                self.cancelled = true
                self.callback = nil
            end,
        }""")
        self.h.lua.globals().test_timer = self.timer
        self.app_module = self.h.lua.execute("""return {
            start = function(deps)
                return { alive = true, seen = 0,
                    transport = deps.transport,
                    fightReceipts = deps.fightReceipts, nativeReadSource = deps.nativeReadSource,
                    files = deps.files, nativePrestigeController = deps.nativePrestigeController,
                    shopQuoteSource = deps.shopQuoteSource,
                    rewardsSource = deps.rewardsSource,
                    globalBossSource = deps.globalBossSource,
                    eventShopSource = deps.eventShopSource,
                    territorySeasonSource = deps.territorySeasonSource, territoryCitySource = deps.territoryCitySource,
                    crateLuckSource = deps.crateLuckSource,
                    bossStages = deps.bossStages,
                    gameData = deps.gameData, config = deps.config,
                    gearSets = deps.gearSets,
                    combatRules = deps.combatRules,
                    Step = function(self, raw)
                        self.seen = self.seen + 1
                        return true
                    end,
                    Destroy = function(self)
                        if not self.alive then return false end
                        self.alive = false
                        deps.onAppClosed()
                        return true
                    end,
                }
            end,
        }""")
        self.observer = self.h.lua.execute("""return {
            Read = function() return {
                place = '73897506680154', account = 'user-a',
                gameVersion = '0.26.530',
                fingerprint = string.rep('a', 64),
            } end,
        }""")
        self.deps = lua_table(self.h.lua, {
            "activateRuntimeHost": True,
            "activateAutomation": True,
            "activateStorage": True,
            "App": self.app_module,
            "NativeSnapshotReader": self.h.load(
                "src/transport/NativeSnapshotReader.luau"),
            "RuntimeDriver": self.h.load(
                "src/transport/RuntimeDriver.luau"),
            "RuntimeLoop": self.h.load(
                "src/transport/RuntimeLoop.luau"),
            "NativeCallPlan": self.h.load(
                "src/transport/NativeCallPlan.luau"),
            "CrewCallPlan": self.h.load(
                "src/tabs/crew/CrewCallPlan.luau"),
            "InventoryCallPlan": self.h.load(
                "src/tabs/inventory/InventoryCallPlan.luau"),
            "CollectionCallPlan": self.h.load(
                "src/tabs/collection/CollectionCallPlan.luau"),
            "CombatCallPlan": self.h.load(
                "src/tabs/combat/CombatCallPlan.luau"),
            "MarketCallPlan": self.h.load(
                "src/tabs/blackMarket/MarketCallPlan.luau"),
            "NativeDispatchAdapter": self.h.load(
                "src/transport/NativeDispatchAdapter.luau"),
            "NativeRemoteResolver": self.h.load(
                "src/transport/NativeRemoteResolver.luau"),
            "RequestLane": self.h.load("src/engine/RequestLane.luau"),
            "ResourceReservations": self.h.load("src/engine/ResourceReservations.luau"),
            "PendingAction": self.h.load("src/storage/PendingAction.luau"),
            "NativeEventAdapter": self.h.load(
                "src/transport/NativeEventAdapter.luau"),
            "ExecutorRuntimeAdapter": self.h.load(
                "src/transport/ExecutorRuntimeAdapter.luau"),
            "executorRuntimeApi": self.h.lua.execute("""return {
                after = function(delay, callback)
                    return test_timer:After(delay, callback)
                end,
                cancel = function(handle)
                    return test_timer:Cancel(handle)
                end,
                queued = {},
                defer = function(callback)
                    local api = test_runtime_api
                    api.queued[#api.queued + 1] = callback
                end,
            }"""),
            "remotesFolder": self.h.lua.execute("""local folder = {
                children = {}, calls = {},
            }
            function folder:FindFirstChild(name)
                return self.children[name]
            end
            local remote = { Parent = folder }
            function remote:IsA(kind)
                return kind == 'RemoteFunction'
            end
            function remote:InvokeServer(...)
                folder.calls[#folder.calls + 1] = table.pack(...)
                return { ok = true }
            end
            folder.children.BossAction = remote
            folder.children.Sync = {
                Parent = folder,
                IsA = function(_, kind) return kind == 'RemoteEvent' end,
                OnClientEvent = {
                    Connect = function(_, callback)
                        return test_events:SubscribeSync(callback)
                    end,
                },
            }
            return folder"""),
            "nativeState": self.h.lua.execute("""return {
                onChanged = function(callback)
                    return test_events:SubscribeChanged(callback)
                end,
            }"""),
            "ExecutorStorageAdapter": self.h.load(
                "src/storage/ExecutorStorageAdapter.luau"),
            "executorStorageApi": self.h.lua.execute("""return {
                isfolder = function() return true end,
                makefolder = function() end,
                isfile = function() return false end,
                readfile = function() return nil end,
                writefile = function() end,
                jsonEncode = function() return '{}' end,
                jsonDecode = function() return {} end,
                hash = function() return string.rep('a', 64) end,
            }"""),
            "identity": self.h.session, "clock": self.h.clock,
            "CompatibilityGate": self.h.load(
                "src/transport/CompatibilityGate.luau"),
            "sourceObserver": self.observer,
            "expectedGameVersion": "0.26.530",
            "fingerprint": "a" * 64,
        })
        self.h.lua.globals().test_runtime_api = self.deps["executorRuntimeApi"]


    def test_family_frame_uses_current_controller_and_resolver_and_closes_owned_source(self):
        self.h.lua.execute("""familyController = {active=true, closed=0, reads=0}
            familyController.Current=function() return familyController.active end
            familyController.Busy=function() return false end
            familyController.Read=function(native)
                familyController.reads=familyController.reads+1
                if native.retire then familyController.active=false end
                return {stamp=native.stamp}
            end
            familyController.Close=function() familyController.active=false;familyController.closed=familyController.closed+1 end
        """)
        controller=self.h.lua.globals().familyController
        self.deps.nativeFamilyBossController=controller
        self.deps.remotesFolder.children.FamilyBossAction=self.h.lua.eval("function(parent) return {Parent=parent,IsA=function(_,kind)return kind=='RemoteFunction'end,InvokeServer=function()end} end")(self.deps.remotesFolder)
        host,reason=self.host_module.start(self.deps)
        self.assertIsNone(reason)
        source=host.app.nativeReadSource
        self.assertIsNotNone(source.FamilyBossFrame)
        self.assertEqual(source.FamilyBossFrame(source,lua_table(self.h.lua,{'stamp':7})).stamp,7)
        self.assertIsNone(source.FamilyBossFrame(source,lua_table(self.h.lua,{'retire':True})))
        host.Destroy(host)
        self.assertGreaterEqual(controller.closed,1)

    def test_recall_owner_created_by_app_gets_shared_plan_transport_and_cleanup(self):
        h=self.h
        self.deps.TerritoryCallPlan=h.load('src/tabs/territory/TerritoryCallPlan.luau')
        self.deps.nativeRecallLease=h.lua.execute('return {Close=function(s) s.closed=true end}')
        h.lua.globals().hostRecallOwner=h.lua.execute("""return {wraps=0,describes=0,
            Describe=function(s,p) s.describes=s.describes+1;return {remote='TerritoryAction',method='InvokeServer',arity=3,args={'recallcrew',7,{}}} end,
            WrapTransport=function(s,base) s.wraps=s.wraps+1;return setmetatable({recallWrapped=true},{__index=function(_,k) local v=base[k];if type(v)=='function' then return function(_,...) return v(base,...) end end;return v end}) end,
            Close=function(s) s.closed=true end}""")
        h.lua.globals().hostBaseApp=self.app_module.start
        self.app_module.start=h.lua.eval("""function(deps)
            assert(hostRecallOwner.wraps==0,'No sender before guarded storage/tab construction')
            deps.nativeRecallRuntime=hostRecallOwner
            return hostBaseApp(deps)
        end""")
        host,why=self.host_module.start(self.deps);self.assertIsNotNone(host,why)
        owner=h.lua.globals().hostRecallOwner
        self.assertEqual(owner.wraps,1);self.assertTrue(host.app.transport.recallWrapped)
        p=h.proposal(feature='station');p.intent=lua_table(h.lua,{'kind':'territoryRecall'})
        self.assertTrue(host.app.transport.Validate(host.app.transport,p)[0]);self.assertEqual(owner.describes,1)
        self.assertEqual(len(self.deps.remotesFolder.calls),0)
        host.Destroy(host);self.assertTrue(owner.closed);self.assertTrue(self.deps.nativeRecallLease.closed)

    def teleport_signal(self):
        self.deps.teleportSignal = self.h.lua.execute("""return {
            disconnected=false,Connect=function(s,callback)
                s.callback=callback
                return {Disconnect=function()s.disconnected=true;s.callback=nil end}
            end}""")
        return self.deps.teleportSignal

    def test_native_server_transfer_closes_host_and_fences_queued_transport(self):
        signal = self.teleport_signal()
        host, reason = self.host_module.start(self.deps)
        self.assertIsNotNone(host, reason)
        self.assertIsNotNone(signal.callback, "Host must subscribe to the server-transfer feed")
        signal.callback(lua_table(self.h.lua, {"Name": "Started"}))
        self.assertFalse(host.active)
        self.assertFalse(host.app.alive)
        self.assertTrue(signal.disconnected)
        self.assertTrue(self.timer.cancelled)
        self.assertEqual(len(self.deps.remotesFolder.calls), 0)

    def test_all_transfer_phases_close_once_and_stale_callbacks_cannot_restart(self):
        for state in ('RequestedFromServer', 'Started', 'WaitingForServer', 'InProgress'):
            with self.subTest(state=state):
                f = RuntimeHostTests(); f.setUp(); signal = f.teleport_signal()
                owner, why = f.host_module.start(f.deps); self.assertIsNone(why)
                callback = signal.callback
                callback(lua_table(f.h.lua, {'Name': state}))
                callback(lua_table(f.h.lua, {'Name': 'Failed'}))
                callback(lua_table(f.h.lua, {'Name': state}))
                self.assertFalse(owner.active); self.assertFalse(owner.app.alive)
                self.assertEqual(owner.transferState, state)
                self.assertEqual(f.events.disconnected, 2)
                self.assertTrue(signal.disconnected)
                self.assertIsNone(f.timer.callback)

    def test_failed_or_invalid_transfer_signal_does_not_close_running_host(self):
        signal = self.teleport_signal(); owner, why = self.host_module.start(self.deps)
        self.assertIsNone(why); self.addCleanup(lambda: owner.Destroy(owner))
        for value in ({'Name': 'Failed'}, {'Name': 'Unknown'}, {}, 'Started', None):
            signal.callback(lua_table(self.h.lua, value) if isinstance(value, dict) else value)
            self.assertTrue(owner.active)
        owner.Destroy(owner); self.assertTrue(signal.disconnected)

    def test_transfer_subscription_failure_closes_app_and_existing_subscriptions(self):
        for body in ("error('unavailable')", 'return {}'):
            with self.subTest(body=body):
                f = RuntimeHostTests(); f.setUp(); signal = f.teleport_signal()
                signal.Connect = f.h.lua.eval('function() '+body+' end')
                owner, why = f.host_module.start(f.deps)
                self.assertIsNone(owner); self.assertEqual(why, 'Teleport subscription failed')
                self.assertEqual(f.events.disconnected, 2); self.assertIsNone(f.timer.callback)

    def test_transfer_during_subscription_closes_before_initial_timer(self):
        signal = self.teleport_signal()
        signal.Connect = self.h.lua.eval("""function(s, callback)
            callback({Name='Started'})
            return {Disconnect=function()s.disconnected=true end} end""")
        owner, why = self.host_module.start(self.deps)
        self.assertIsNone(owner); self.assertEqual(why, 'Server transfer interrupted startup')
        self.assertTrue(signal.disconnected); self.assertEqual(self.events.disconnected, 2)
        self.assertIsNone(self.timer.callback)

    def test_events_tick_and_ui_unload_disconnect(self):
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        self.assertIsNotNone(host.app.transport.Send)
        self.assertIsNotNone(host.app.files.ReadFile)
        self.events.sync(lua_table(self.h.lua, {"cash": 10}))
        self.assertEqual(host.app.seen, 0)
        self.events.changed(lua_table(self.h.lua, {"cash": 11}))
        self.assertEqual(host.app.seen, 0)
        self.timer.callback()
        self.assertEqual(host.app.seen, 2)
        host.app.Destroy(host.app)
        self.assertFalse(host.alive)
        self.assertFalse(host.active)
        self.assertEqual(self.events.disconnected, 2)
        self.assertTrue(self.timer.cancelled)
        self.assertFalse(host.Destroy(host))

    def test_subscription_failure_unwinds_app_and_first_handle(self):
        self.events["SubscribeChanged"] = self.h.lua.eval(
            "function() error('unavailable') end")
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(host)
        self.assertEqual(reason, "Changed-state subscription failed")
        self.assertEqual(self.events.disconnected, 1)
        self.assertIsNone(self.events.sync)

    def test_requires_explicit_storage_and_automation_activation(self):
        self.deps["activateStorage"] = False
        self.assertIsNone(self.host_module.start(self.deps)[0])
        self.assertIsNone(self.events.sync)

    def test_optional_prestige_domain_wrapper_is_bound_without_invoking_reset(self):
        self.deps.PrestigeReset = self.h.load("src/tabs/prestige/PrestigeReset.luau")
        called = self.h.lua.table()
        self.h.lua.globals().prestigeWrapperCalled = called
        self.h.lua.globals().originalPrestigeWrapper = self.deps.NativeCallPlan.withPrestige
        self.deps.NativeCallPlan.withPrestige = self.h.lua.eval("""function(base, domain)
            prestigeWrapperCalled[1] = domain
            return originalPrestigeWrapper(base, domain)
        end""")
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        self.assertIsNotNone(called[1].describe)
        self.assertEqual(len(self.deps.remotesFolder.calls), 0)
        host.Destroy(host)

    def current_client(self):
        self.h.lua.globals().real_teleport_signal = self.teleport_signal()
        self.h.lua.globals().real_player_gui = self.h.lua.table_from({"Name":"PlayerGui"})
        self.h.lua.globals().real_folder = self.deps["remotesFolder"]
        self.h.lua.globals().real_state = self.deps["nativeState"]
        self.deps["nativeState"]["latest"] = self.h.lua.eval(
            "function() return { cash = 10 } end")
        self.h.lua.globals().real_observer = self.observer
        self.h.lua.globals().real_runtime_api = self.deps["executorRuntimeApi"]
        self.h.lua.globals().real_storage_api = self.deps["executorStorageApi"]
        self.h.lua.globals().real_clock = self.deps["clock"]
        self.h.lua.globals().real_rewards_rule = self.h.lua.execute("""return {
            isWeekend = function() return true end,
        }""")
        self.h.lua.globals().real_event_shop = self.h.lua.execute("""return {
            definition={MEDAL='event_medal',MAX_ITEM_COUNT=99,ROWS={
                {key='gold',item='gold_bar',kind='item',price=3,count=1}}},
            readAttributes=function() return {GlobalEventShop=true,GlobalEventShopEnd=2000} end} """)
        self.h.lua.globals().real_territory_season = self.h.lua.execute("""return {
            readLive=function() return {season=2,startsAt=900,endsAt=2000} end,
            status=function(live,now) return {phase='running',n=live.season,
                startsAt=live.startsAt,endsAt=live.endsAt} end} """)
        self.deps["nativePrestigeController"] = self.h.lua.table_from({"injected": True})
        self.deps["activateCurrentClient"] = True
        self.deps["clientGame"] = self.h.lua.table()
        self.deps["clientRequire"] = self.h.lua.eval("function() end")
        self.deps["clientHash"] = self.h.lua.eval("function() end")
        self.deps["NativeClientBindings"] = self.h.lua.execute("""return {
            read = function() return {
                remotesFolder = real_folder, nativeState = real_state,
                uiParent = real_player_gui, teleportSignal = real_teleport_signal,
                currentDailyBuffRules = real_rewards_rule,
                currentPrestigeController = {Read=function() end, Current=function() return true end,
                    Close=function(self) self.closed=true end},
                config = { GROUP = { id = 123 }, COMBAT = { staminaCost = 2 } },
                gameData = { JOBS = { { id = 'j_watch' } } },
                gearSets = { slotBonus = function() end },
                combatRules = { staminaCost = 2 },
                currentShop = real_shop_source,
                currentEventShop = real_event_shop,
                currentTerritorySeason = real_territory_season,
                currentCrateLuck = { crateLuck = function(native)
                    return native.luckBonus end },
                bossStages = { MAX_STAGE = 100000 },
                groupLookup = function(id) return id == 123 end,
            } end,
        }""")
        self.deps["NativeRewardsSource"] = self.h.load(
            "src/tabs/rewards/NativeRewardsSource.luau")
        self.deps["NativeCrateLuckSource"] = self.h.load(
            "src/tabs/inventory/NativeCrateLuckSource.luau")
        self.deps.NativeEventShopSource = self.h.load('src/tabs/events/NativeEventShopSource.luau')
        self.deps.currentEventShop = self.h.lua.table_from({'definition': 'caller-fake'})
        self.deps.TerritorySeasonSource = self.h.load('src/tabs/territory/TerritorySeasonSource.luau')
        self.deps.currentTerritorySeason = self.h.lua.table_from({'readLive': 'caller-fake'})
        self.deps["release"] = "release-a"
        self.deps["config"] = lua_table(self.h.lua, {
            "GROUP": {"id": 999}})
        self.deps["gameData"] = lua_table(self.h.lua, {
            "JOBS": [{"id": "caller-fake"}]})
        self.deps["gearSets"] = self.h.lua.table()
        self.deps["combatRules"] = lua_table(self.h.lua, {
            "staminaCost": 999})
        self.deps["currentDailyBuffRules"] = self.h.lua.table()
        self.deps["groupLookup"] = self.h.lua.eval(
            "function() return false end")
        self.deps["currentShop"] = self.h.lua.table()
        self.h.lua.globals().real_runtime_api.readNative = self.h.lua.eval("function(fn, ...) return pcall(fn, ...) end")
        self.deps["NativeQuoteSource"] = self.h.lua.execute("""return {
            new = function(current, release, key, readNative)
                return { current = current, release = release,
                    catalogKey = key, readNative = readNative }, nil
            end,
        }""")
        self.deps["NativeClientObserver"] = self.h.lua.execute("""return {
            new = function() return real_observer end,
        }""")
        self.deps["NativeExecutorCapabilities"] = self.h.lua.execute("""return {
            new = function() return {
                executorRuntimeApi = real_runtime_api,
                executorStorageApi = real_storage_api,
                clock = real_clock,
            } end,
        }""")
        self.deps["executorEnv"] = self.h.lua.table()
        self.deps["scheduler"] = self.h.lua.table()
        self.deps["httpService"] = self.h.lua.table()
        self.deps["remotesFolder"] = None
        self.deps["nativeState"] = None
        self.deps["sourceObserver"] = self.h.lua.execute("""return {
            Read = function() return nil end,
        }""")
        self.deps["executorRuntimeApi"] = None
        self.deps["executorStorageApi"] = None
        self.deps["clock"] = None
    def test_current_client_waits_for_observed_sync_and_ignores_income_projection(self):
        self.current_client()
        owner,why=self.host_module.start(self.deps)
        self.assertIsNone(why);self.addCleanup(lambda:owner.Destroy(owner))
        reader=owner.driver.reader
        self.assertIsNone(reader.Capture(reader)[0])
        self.events.sync(lua_table(self.h.lua,{"cash":5}))
        self.events.changed(lua_table(self.h.lua,{"cash":6.5}))
        observed=reader.Capture(reader)[0]
        self.assertTrue(observed.native.fullSync)
        self.assertEqual(observed.native.cash,5)

    def test_current_client_transfer_feed_cannot_be_replaced_by_caller(self):
        self.current_client()
        native = self.h.lua.globals().real_teleport_signal
        injected = self.teleport_signal()
        owner, why = self.host_module.start(self.deps)
        self.assertIsNone(why); self.addCleanup(lambda: owner.Destroy(owner))
        self.assertIsNone(injected.callback); self.assertIsNotNone(native.callback)
        native.callback(lua_table(self.h.lua, {'Name':'Started'}))
        self.assertFalse(owner.active); self.assertTrue(native.disconnected)

    def test_current_client_requires_native_transfer_feed(self):
        self.current_client(); self.h.lua.globals().real_teleport_signal = None
        owner, why = self.host_module.start(self.deps)
        self.assertIsNone(owner); self.assertEqual(why, 'Current local-player teleport feed unavailable')
        self.assertIsNone(self.events.sync); self.assertIsNone(self.timer.callback)

    def test_current_client_requires_owned_player_gui_before_constructing_ui(self):
        self.current_client()
        self.h.lua.globals().real_player_gui = None
        owner,why=self.host_module.start(self.deps)
        self.assertIsNone(owner)
        self.assertIn('bindings',why)
        self.assertIsNone(self.events.sync)

    def test_current_client_mode_uses_resolved_bindings_and_observer(self):
        self.current_client()
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        self.assertIsNotNone(host)
        self.assertIsNotNone(self.events.sync)
        self.assertEqual(host.app.seen, 0)
        self.assertIsNotNone(host.app.nativePrestigeController.Read)
        self.assertIsNone(host.app.nativePrestigeController.injected)
        self.timer.callback()
        self.assertEqual(host.app.seen, 0)
        self.events.sync(lua_table(self.h.lua,{"cash":10}))
        self.assertEqual(host.app.seen, 0)
        self.timer.callback()
        self.assertEqual(host.app.seen, 1)
        self.assertEqual(host.app.rewardsSource.groupId, 123)
        self.assertTrue(host.app.rewardsSource.IsWeekend(
            host.app.rewardsSource, 0))
        self.assertEqual(host.app.gameData.JOBS[1].id, 'j_watch')
        self.assertEqual(host.app.config.GROUP.id, 123)
        self.assertIsNotNone(host.app.gearSets.slotBonus)
        self.assertEqual(host.app.combatRules.staminaCost, 2)
        self.assertEqual(host.app.bossStages.MAX_STAGE, 100000)
        event_raw = self.h.snapshot(native={'fullSync': True,'serverNow': 1000})
        event_enriched = host.app.eventShopSource.Enrich(host.app.eventShopSource, event_raw)[0]
        self.assertEqual(event_enriched.eventShopProof.offers.gold.price, 3)
        season_enriched = host.app.territorySeasonSource.Enrich(host.app.territorySeasonSource, event_raw)[0]
        self.assertEqual(season_enriched.territorySeason.n, 2)
        self.assertEqual(host.app.crateLuckSource.Read(
            host.app.crateLuckSource,
            lua_table(self.h.lua, {"luckBonus": 0.4})), 0.4)
        self.assertIsNone(host.app.shopQuoteSource)
        prestige_source = host.app.nativePrestigeController
        host.Destroy(host)
        self.assertTrue(prestige_source.closed)
        self.assertIsNone(self.deps.nativePrestigeController.closed)
        native_shop = self.h.lua.table()
        self.h.lua.globals().real_shop_source = native_shop
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        same = self.h.lua.eval("function(a, b) return a == b end")
        self.assertTrue(same(host.app.shopQuoteSource.current,
                             native_shop))
        self.assertTrue(same(host.app.shopQuoteSource.readNative,
                             self.h.lua.globals().real_runtime_api.readNative))
        host.Destroy(host)

    def test_current_shop_without_owned_read_capability_stays_unavailable(self):
        self.current_client()
        self.h.lua.globals().real_shop_source = self.h.lua.table()
        self.h.lua.globals().real_runtime_api.readNative = None
        self.deps.readNative = self.h.lua.eval("function(fn) return pcall(fn) end")
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        self.assertIsNone(host.app.shopQuoteSource)
        host.Destroy(host)

    def test_current_territory_city_source_replaces_caller_and_missing_native_source_stays_missing(self):
        self.current_client()
        self.deps.territoryCitySource = lua_table(self.h.lua, {"injected": True})
        host, why = self.host_module.start(self.deps)
        self.assertIsNone(why)
        self.assertIsNone(host.app.territoryCitySource)
        host.Destroy(host)
        self.h.lua.globals().cityBindingRead = self.deps.NativeClientBindings.read
        self.h.lua.globals().nativeCities = self.h.lua.execute("return {Current=function() return true end,Select=function() return {cityId='jade_harbor'} end}")
        self.deps.NativeClientBindings.read = self.h.lua.eval("function(...) local value=cityBindingRead(...);value.currentTerritoryCities=nativeCities;return value end")
        host, why = self.host_module.start(self.deps)
        self.assertIsNone(why)
        self.assertIsNone(host.app.territoryCitySource.injected)
        self.assertEqual(host.app.territoryCitySource.Select(host.app.territoryCitySource).cityId, "jade_harbor")
        host.Destroy(host)

    def test_closed_combat_cleanup_precedes_fresh_binding_capture(self):
        self.current_client()
        self.deps.executionRegistry = self.h.lua.eval("{closedProxy=true}")
        self.h.lua.globals().cleanupRegistry = self.deps.executionRegistry
        self.h.lua.globals().freshBindings = self.deps.NativeClientBindings.read
        self.deps.NativeCombatLease = self.h.lua.eval("""{cleanup=function(registry)
            assert(registry==cleanupRegistry)
            registry.closedProxy=false
            registry.cleanups=(registry.cleanups or 0)+1
            return true
        end}""")
        self.deps.NativeClientBindings.read = self.h.lua.eval("""function(...)
            assert(cleanupRegistry.closedProxy==false, 'Captured stale Combat proxy')
            return freshBindings(...)
        end""")
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        self.assertIsNotNone(host)
        self.assertEqual(self.deps.executionRegistry.cleanups, 1)
        host.Destroy(host)

    def test_unconfirmed_combat_cleanup_stops_before_binding_or_app(self):
        self.current_client()
        for mode in ('reject', 'raise'):
            with self.subTest(mode=mode):
                self.h.lua.globals().cleanupRegistry = self.h.lua.eval("{bindingReads=0}")
                self.deps.executionRegistry = self.h.lua.globals().cleanupRegistry
                self.deps.NativeClientBindings.read = self.h.lua.eval("""function()
                    cleanupRegistry.bindingReads=cleanupRegistry.bindingReads+1
                    error('Must not capture an unclean proxy')
                end""")
                self.deps.NativeCombatLease = self.h.lua.eval("""{cleanup=function()
                    return false, 'Exact previous owner still holds proxy custody'
                end}""" if mode=='reject' else """{cleanup=function()
                    error('Previous owner unavailable')
                end}""")
                host, reason = self.host_module.start(self.deps)
                self.assertIsNone(host)
                self.assertIn('Combat cleanup', reason)
                self.assertEqual(self.deps.executionRegistry.bindingReads, 0)
                self.assertIsNone(self.events.sync)

    def test_native_prestige_owner_replaces_and_closes_unused_readonly_observer(self):
        self.current_client()
        self.deps.executionRegistry=self.h.lua.table()
        self.h.lua.globals().readPrestigeBindings=self.deps.NativeClientBindings.read
        self.deps.NativeClientBindings.read=self.h.lua.eval("""function(...)
            local b=readPrestigeBindings(...);oldPrestigeObserver=b.currentPrestigeController;return b
        end""")
        self.h.lua.execute("""prestigeOwner={closed=false,Read=function()return {}end,Current=function()return true end,
            Acquire=function()return true end,Owns=function()return true end,Invoke=function()end,
            Release=function()end,Status=function()return {active=false,physical=false,closed=false}end,
            Close=function(s)s.closed=true;return true end}""")
        self.deps.NativePrestigeLease=self.h.lua.eval("""{cleanup=function()return true end,
            bind=function(d)prestigeOwner.bindIdentity=d.identity;return prestigeOwner end}""")
        host,why=self.host_module.start(self.deps)
        self.assertIsNotNone(host,why)
        self.assertTrue(self.h.lua.globals().oldPrestigeObserver.closed)
        self.assertIsNotNone(host.app.nativePrestigeController.bindIdentity)
        self.assertTrue(host.app.transport.requirePrestigeLease)
        self.assertIsNotNone(host.app.transport.prestigeLease)
        host.Destroy(host)
        self.assertTrue(self.h.lua.globals().prestigeOwner.closed)

    def test_failed_prestige_binding_cannot_keep_readonly_observer_as_reset_authority(self):
        self.current_client()
        self.deps.NativePrestigeLease=self.h.lua.eval("""{cleanup=function()return true end,
            bind=function()return nil,'Native controller not available'end}""")
        host,why=self.host_module.start(self.deps)
        self.assertIsNotNone(host,why)
        self.assertIsNone(host.app.nativePrestigeController)
        self.assertIsNone(host.app.transport.prestigeLease)
        self.assertTrue(host.app.transport.requirePrestigeLease)
        host.Destroy(host)

    def test_prestige_cleanup_refusal_holds_before_binding_capture(self):
        self.current_client()
        self.deps.NativePrestigeLease=self.h.lua.eval("""{cleanup=function()
            return false,'Native request still physically unresolved'end}""")
        self.deps.NativeClientBindings.read=self.h.lua.eval("function()error('Must not capture')end")
        host,why=self.host_module.start(self.deps)
        self.assertIsNone(host)
        self.assertIn('Prestige cleanup',why)
        self.assertIsNone(self.events.sync)

    def test_unbound_native_proof_sources_override_caller_values(self):
        self.deps["shopQuoteSource"] = self.h.lua.table_from({"fake": True})
        self.deps["rewardsSource"] = self.h.lua.table_from({"fake": True})
        self.deps["crateLuckSource"] = self.h.lua.table_from({"fake": True})
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        self.assertIsNone(host.app.shopQuoteSource)
        self.assertIsNone(host.app.rewardsSource)
        self.assertIsNone(host.app.crateLuckSource)
        host.Destroy(host)

    def test_optional_pinned_native_proof_sources_are_constructed(self):
        self.deps["NativeQuoteSource"] = self.h.lua.execute("""return {
            new = function(current, release, key)
                return { release = release, catalogKey = key }, nil
            end,
        }""")
        self.deps["currentShop"] = self.h.lua.table()
        self.deps["NativeRewardsSource"] = self.h.lua.execute("""return {
            new = function(rule, lookup, clock, release, account, id)
                return { release = release, account = account,
                    groupId = id,
                    Close = function(self) self.closed = true end }, nil
            end,
        }""")
        self.deps["currentDailyBuffRules"] = self.h.lua.table()
        self.deps["groupLookup"] = self.h.lua.eval(
            "function() return true end")
        self.deps["config"] = lua_table(self.h.lua, {
            "GROUP": {"id": 674050067}})
        self.deps["release"] = "release-a"
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        self.assertEqual(host.app.shopQuoteSource["catalogKey"],
                         "a" * 64)
        self.assertEqual(host.app.rewardsSource["account"], "user-a")
        source = host.app.rewardsSource
        host.Destroy(host)
        self.assertTrue(source.closed)

    def test_group_refresh_is_queued_once_and_closed_callback_is_fenced(self):
        self.deps["NativeRewardsSource"] = self.h.lua.execute("""return {
            new = function(rule, lookup, clock, release, account, id)
                return { release = release, account = account,
                    groupId = id, calls = 0,
                    Membership = function(self)
                        if self.calls == 0 then return nil end
                        return true, 0
                    end,
                    Refresh = function(self)
                        self.calls = self.calls + 1
                        return true
                    end,
                    Close = function(self) self.closed = true end }, nil
            end,
        }""")
        self.deps["currentDailyBuffRules"] = self.h.lua.table()
        self.deps["groupLookup"] = self.h.lua.eval(
            "function() return true end")
        self.deps["config"] = lua_table(self.h.lua, {
            "GROUP": {"id": 674050067}})
        self.deps["release"] = "release-a"
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        self.events.sync(lua_table(self.h.lua, {"cash": 10}))
        self.events.sync(lua_table(self.h.lua, {"cash": 11}))
        queued = self.deps["executorRuntimeApi"]["queued"]
        self.assertEqual(len(queued), 1)
        queued[1]()
        self.assertEqual(host.app.rewardsSource["calls"], 1)
        self.events.sync(lua_table(self.h.lua, {"cash": 12}))
        self.assertEqual(len(queued), 1)
        self.assertTrue(host.RefreshGroupMembership(host))
        host.Destroy(host)
        queued[2]()
        self.assertEqual(host.app.rewardsSource["calls"], 1)

    def test_group_refresh_can_retry_after_scheduler_declines(self):
        self.deps["NativeRewardsSource"] = self.h.lua.execute("""return {
            new = function(_, _, _, release, account, id)
                return { release = release, account = account,
                    groupId = id, Refresh = function() return true end }, nil
            end,
        }""")
        self.deps["currentDailyBuffRules"] = self.h.lua.table()
        self.deps["groupLookup"] = self.h.lua.eval(
            "function() return true end")
        self.deps["config"] = lua_table(self.h.lua, {
            "GROUP": {"id": 674050067}})
        self.deps["release"] = "release-a"
        self.deps["executorRuntimeApi"]["defer"] = self.h.lua.execute(
            """local declined = false
            return function(callback)
                if not declined then declined = true; return false end
                local api = test_runtime_api
                api.queued[#api.queued + 1] = callback
                return true
            end""")
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        self.assertFalse(host.RefreshGroupMembership(host))
        self.assertTrue(host.RefreshGroupMembership(host))
        self.assertEqual(len(self.deps["executorRuntimeApi"]["queued"]), 1)
        host.Destroy(host)

    def test_incompatible_client_never_starts_app_or_subscribes(self):
        self.observer["Read"] = self.h.lua.eval("""function()
            return { place = '73897506680154',
                account = 'user-a',
                gameVersion = '0.26.531',
                fingerprint = string.rep('a', 64) }
        end""")
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(host)
        self.assertEqual(reason,
            "Current client compatibility not verified: "
            "Current game version differs from reviewed source")
        self.assertIsNone(self.events.sync)

    def test_fingerprint_mismatch_reports_specific_gate_without_starting(self):
        self.observer["Read"] = self.h.lua.eval("""function()
            return { place = '73897506680154',
                account = 'user-a', gameVersion = '0.26.530',
                fingerprint = string.rep('b', 64) }
        end""")
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(host)
        self.assertEqual(reason,
            "Current client compatibility not verified: "
            "Current source fingerprint differs")
        self.assertIsNone(self.events.sync)

    def test_prestige_source_is_closed_when_app_startup_fails(self):
        for failure in ('raise','invalid'):
            source=self.h.lua.execute('return {Close=function(self) self.closed=true end}')
            self.deps.nativePrestigeController=source
            body="error('construction failed')" if failure=='raise' else 'return {}'
            self.deps.App=self.h.lua.execute('return {start=function(deps) '+body+' end}')
            host,reason=self.host_module.start(self.deps)
            self.assertIsNone(host);self.assertIsNotNone(reason);self.assertTrue(source.closed)
            self.assertIsNone(self.events.sync)

    def test_partial_app_startup_is_destroyed(self):
        self.h.lua.globals().partial_app_destroyed = False
        self.deps["App"] = self.h.lua.execute("""return {
            start = function(deps)
                return { alive = true,
                    Destroy = function()
                        partial_app_destroyed = true
                        deps.onAppClosed()
                    end,
                }
            end,
        }""")
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(host)
        self.assertEqual(reason, "App startup returned invalid handle")
        self.assertTrue(self.h.lua.globals().partial_app_destroyed)
        self.assertIsNone(self.events.sync)

    def test_app_exception_reports_first_line_and_cleans_up(self):
        self.deps["App"] = self.h.lua.execute("""return {
            start = function()
                error([[Missing current source
extra private details]])
            end,
        }""")
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(host)
        self.assertIn("App construction raised:", reason)
        self.assertIn("Missing current source", reason)
        self.assertNotIn("extra private details", reason)
        self.assertLessEqual(len(reason), 120)
        self.assertIsNone(self.events.sync)

    def test_source_change_before_next_sync_closes_host(self):
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        self.observer["Read"] = self.h.lua.eval("""function()
            return { place = '73897506680154',
                account = 'user-a',
                gameVersion = '0.26.531',
                fingerprint = string.rep('a', 64) }
        end""")
        self.events.sync(lua_table(self.h.lua, {"cash": 10}))
        self.assertFalse(host.alive)
        self.assertEqual(host.app.seen, 0)
        self.assertEqual(self.events.disconnected, 2)

    def test_dispatch_resolves_current_remote_and_closes_with_host(self):
        self.deps["executorRuntimeApi"]["invoke"] = self.h.lua.eval(
            "function() error('caller invoker used') end")
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        proposal = self.h.proposal(feature="bossShop", key="shop:gear:1")
        proposal["intent"] = lua_table(self.h.lua, {
            "kind": "bossShopBuy", "item": "w_policebaton",
            "itemKind": "gear", "quantity": 1})
        transport = host.app.transport
        transport.Send(transport, proposal,
            self.h.lua.eval("function(_reply) end"),
            self.h.lua.eval("function() return true end"))
        self.assertEqual(len(self.deps["remotesFolder"]["calls"]), 0)
        self.deps["executorRuntimeApi"]["queued"][1]()
        args = self.deps["remotesFolder"]["calls"][1]
        self.assertEqual(args["n"], 3)
        self.assertIsNone(args[3])
        host.Destroy(host)
        self.assertFalse(transport.Send(transport, proposal,
            self.h.lua.eval("function(_reply) end"),
            self.h.lua.eval("function() return true end")))
        self.assertEqual(len(self.deps["executorRuntimeApi"]["queued"]), 1)
        self.assertEqual(len(self.deps["remotesFolder"]["calls"]), 1)

    def test_missing_current_remote_blocks_send_without_fallback(self):
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        self.deps["remotesFolder"]["children"]["BossAction"] = None
        proposal = self.h.proposal(feature="bossShop", key="shop:gear:1")
        proposal["intent"] = lua_table(self.h.lua, {
            "kind": "bossShopBuy", "item": "w_policebaton",
            "itemKind": "gear", "quantity": 1})
        host.app.transport.Send(host.app.transport, proposal,
            self.h.lua.eval("function(_reply) end"),
            self.h.lua.eval("function() return true end"))
        self.deps["executorRuntimeApi"]["queued"][1]()
        self.assertEqual(len(self.deps["remotesFolder"]["calls"]), 0)
        host.Destroy(host)

    def test_source_change_before_queued_dispatch_closes_host(self):
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        proposal = self.h.proposal(feature="bossShop", key="shop:gear:1")
        proposal["intent"] = lua_table(self.h.lua, {
            "kind": "bossShopBuy", "item": "w_policebaton",
            "itemKind": "gear", "quantity": 1})
        host.app.transport.Send(host.app.transport, proposal,
            self.h.lua.eval("function(_reply) end"),
            self.h.lua.eval("function() return true end"))
        self.observer["Read"] = self.h.lua.eval("""function()
            return { place = '73897506680154',
                account = 'user-a',
                gameVersion = '0.26.531',
                fingerprint = string.rep('a', 64) }
        end""")
        self.deps["executorRuntimeApi"]["queued"][1]()
        self.assertFalse(host.active)
        self.assertEqual(len(self.deps["remotesFolder"]["calls"]), 0)

    def test_account_change_before_queued_dispatch_closes_host(self):
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        proposal = self.h.proposal(feature="bossShop", key="shop:gear:1")
        proposal["intent"] = lua_table(self.h.lua, {
            "kind": "bossShopBuy", "item": "w_policebaton",
            "itemKind": "gear", "quantity": 1})
        host.app.transport.Send(host.app.transport, proposal,
            self.h.lua.eval("function(_reply) end"),
            self.h.lua.eval("function() return true end"))
        self.observer["Read"] = self.h.lua.eval("""function()
            return { place = '73897506680154',
                account = 'user-b', gameVersion = '0.26.530',
                fingerprint = string.rep('a', 64) }
        end""")
        self.deps["executorRuntimeApi"]["queued"][1]()
        self.assertFalse(host.active)
        self.assertEqual(len(self.deps["remotesFolder"]["calls"]), 0)


    def test_event_shop_host_binds_actual_source_and_closes_it(self):
        self.deps.NativeEventShopSource = self.h.load('src/tabs/events/NativeEventShopSource.luau')
        self.deps.release = 'release-a'
        self.deps.currentEventShop = self.h.lua.execute("""return {
            definition={MEDAL='event_medal',MAX_ITEM_COUNT=99,ROWS={
                {key='gold',item='gold_bar',kind='item',price=3,count=1}}},
            readAttributes=function() return {GlobalEventShop=true,
                GlobalEventShopEnd=2000,MWPaidRandomRestricted=true} end} """)
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        source = host.app.eventShopSource
        self.assertIsNotNone(source)
        raw = self.h.snapshot(native={'fullSync': True, 'serverNow': 1000})
        enriched, reason = source.Enrich(source, raw)
        self.assertIsNone(reason)
        self.assertEqual(source.Read(source, enriched, enriched)[0].offers.gold.price, 3)
        self.assertEqual(len(self.deps.remotesFolder.calls), 0)
        host.Destroy(host)
        self.assertIsNone(source.Enrich(source, raw)[0])

    def test_territory_season_host_constructs_and_closes_read_only_source(self):
        self.deps.TerritorySeasonSource = self.h.load('src/tabs/territory/TerritorySeasonSource.luau')
        self.deps.release = 'release-a'
        self.deps.currentTerritorySeason = self.h.lua.execute("""return {
            readLive=function() return {season=2,startsAt=900,endsAt=2000} end,
            status=function(live, now) return {phase='running',n=live.season,
                startsAt=live.startsAt,endsAt=live.endsAt} end} """)
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        source = host.app.territorySeasonSource
        self.assertIsNotNone(source)
        raw = self.h.snapshot(native={'fullSync': True,'serverNow': 1000})
        enriched = source.Enrich(source, raw)[0]
        self.assertEqual(source.Read(source, enriched, raw)[0].n, 2)
        self.assertEqual(len(self.deps.remotesFolder.calls), 0)
        host.Destroy(host)
        self.assertIsNone(source.Enrich(source, raw)[0])

    def test_event_shop_missing_or_invalid_binding_discards_injected_source(self):
        self.deps.NativeEventShopSource = self.h.load('src/tabs/events/NativeEventShopSource.luau')
        self.deps.release = 'release-a'
        self.deps.eventShopSource = self.h.lua.table_from({'forged': True})
        for current in (None, self.h.lua.table_from({'definition': 'bad'})):
            self.deps.currentEventShop = current
            host, reason = self.host_module.start(self.deps)
            self.assertIsNone(reason)
            self.assertIsNone(host.app.eventShopSource)
            self.assertEqual(len(self.deps.remotesFolder.calls), 0)
            host.Destroy(host)

    def test_global_boss_native_attribute_source_is_bound_and_closed(self):
        self.deps.NativeGlobalBossSource = self.h.load("src/tabs/combat/NativeGlobalBossSource.luau")
        self.deps.GlobalBossState = self.h.load("src/game/GlobalBossState.luau")
        self.deps.release = "release-a"
        self.deps.currentGlobalBoss = self.h.lua.execute("""return {userId=42,
            readAttributes=function() return {} end,
            rule={ATTR='GlobalBossState',PRIVATE_ATTR='GlobalBossPrivateState',
                decode=function() return nil end,canAccess=function() return true end}}""")
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        source = host.app.globalBossSource
        self.assertIsNotNone(source)
        raw = self.h.snapshot(native={"fullSync": True,"serverNow":100})
        self.assertIsNotNone(source.Enrich(source, raw)[0])
        host.Destroy(host)
        self.assertIsNone(source.Enrich(source, raw)[0])


    def test_graceful_app_flush_runs_before_receipt_sources_and_lane_close(self):
        h=self.h
        self.deps.FightReceipts=h.load('src/tabs/combat/FightReceipts.luau')
        self.deps.nativeFightNotifications=h.lua.execute("return {Current=function() return true end,CanAttack=function() return true end,Subscribe=function() return {Disconnect=function() end} end}")
        h.lua.globals().originalHostAppStart=self.app_module.start
        self.app_module.start=h.lua.eval("""function(deps)
            local app=originalHostAppStart(deps);local destroy=app.Destroy
            function app:Destroy()
                self.flushHadReceiptSource=deps.fightReceipts:Read(hostCloseRaw)~=nil
                self.flushHadLease=hostCloseLane:Owns(hostCloseToken)
                return destroy(self)
            end
            return app
        end""")
        host,why=self.host_module.start(self.deps);self.assertIsNotNone(host,why)
        token=host.requestLane.TryAcquire(host.requestLane,'mutation','combat:close',45)[0]
        h.lua.globals().hostCloseLane=host.requestLane;h.lua.globals().hostCloseToken=token
        h.lua.globals().hostCloseRaw=h.snapshot(native={'fullSync':True})
        host.Destroy(host)
        self.assertTrue(host.app.flushHadReceiptSource);self.assertTrue(host.app.flushHadLease)
        self.assertIsNone(host.app.fightReceipts.Read(host.app.fightReceipts,h.lua.globals().hostCloseRaw));self.assertTrue(host.requestLane.Status(host.requestLane).closed)

    def test_current_fight_receipt_owner_is_lazy_and_closed_with_host(self):
        self.deps.FightReceipts=self.h.load("src/tabs/combat/FightReceipts.luau")
        source=self.h.lua.execute("""return {callback=nil,disconnected=0,
            CanAttack=function() return true end,Current=function() return true end,
            Subscribe=function(self,cb) self.callback=cb;return {Disconnect=function() self.disconnected=self.disconnected+1 end} end}""")
        self.deps.nativeFightNotifications=source
        host,why=self.host_module.start(self.deps);self.assertIsNotNone(host,why)
        owner=host.app.fightReceipts;self.assertIsNotNone(owner);self.assertIsNone(source.callback)
        token=host.requestLane.TryAcquire(host.requestLane,"mutation","combat:42",45)[0]
        proposal=lua_table(self.h.lua,{**self.h.session,"feature":"combat","actionKey":"combat:42","resources":{"stamina":1},"intent":{"kind":"playerAttack","target":42}})
        self.assertTrue(owner.Begin(owner,token,proposal,42)[0]);cb=source.callback
        host.Destroy(host);self.assertEqual(source.disconnected,1)
        cb("fightcash","",self.h.lua.table());self.assertIsNone(owner.Read(owner,self.h.snapshot()))

    def test_host_transport_uses_current_native_wrapper_for_business_arguments(self):
        self.h.lua.globals().wrapperFolder=self.deps.remotesFolder
        self.deps.nativeRemoteLink=self.h.lua.execute("""local raw=wrapperFolder.children.BossAction
            local wrapped={Name='BossAction',Instance=raw}
            function wrapped:InvokeServer(...) return raw:InvokeServer('fixture-native-header',...) end
            return {Current=function() return true end,Resolve=function(_,name) assert(name=='BossAction');return wrapped end}""")
        host,why=self.host_module.start(self.deps);self.assertIsNotNone(host,why)
        proposal=self.h.proposal();proposal.feature='bosses'
        proposal.intent=lua_table(self.h.lua,{'kind':'bossStageAttack','stage':2})
        self.assertTrue(host.app.transport.Send(host.app.transport,proposal,self.h.lua.eval('function() end'),self.h.lua.eval('function() return true end')))
        self.deps.executorRuntimeApi.queued[1]()
        args=self.deps.remotesFolder.calls[1]
        self.assertEqual((args.n,args[1],args[2],args[3]),(3,'fixture-native-header','stageAttack',2))
        host.Destroy(host)


    def test_friendship_read_source_uses_pinned_native_api_and_preserves_unknown(self):
        self.deps.remotesFolder.children.PlayerProfile=self.deps.remotesFolder.children.BossAction
        self.deps.nativeFightNotifications=self.h.lua.execute("""return {valid=true,
            Current=function(self) return self.valid end,Subscribe=function() return {Disconnect=function() end} end,
            Friendship=function(_,target) return target==42 end}""")
        host,why=self.host_module.start(self.deps);self.assertIsNotNone(host,why)
        source=host.app.nativeReadSource
        self.assertTrue(source.Friendship(source,42));self.assertFalse(source.Friendship(source,43))
        self.deps.nativeFightNotifications.valid=False;self.assertIsNone(source.Friendship(source,42))
        host.Destroy(host);self.assertIsNone(source.Friendship(source,42))


    def test_native_combat_frame_proxy_is_pinned_and_closed_without_remote_calls(self):
        self.deps.remotesFolder.children.GetHitList=self.deps.remotesFolder.children.BossAction
        self.deps.nativeFightNotifications=self.h.lua.execute("""return {Current=function() return true end,
            CombatFrame=function(self) self.frameCalls=(self.frameCalls or 0)+1;return {attack=200} end}""")
        host,why=self.host_module.start(self.deps);self.assertIsNotNone(host,why)
        source=host.app.nativeReadSource
        self.assertEqual(source.CombatFrame(source,self.h.lua.table(),self.h.lua.table()).attack,200)
        self.assertEqual(len(self.deps.remotesFolder.calls),0)
        self.deps.nativeFightNotifications.CombatFrame=self.h.lua.eval('function() error("changed frame") end')
        self.assertIsNone(source.CombatFrame(source,self.h.lua.table(),self.h.lua.table()))
        host.Destroy(host);self.assertIsNone(source.CombatFrame(source,self.h.lua.table(),self.h.lua.table()))

if __name__ == "__main__":
    unittest.main()
