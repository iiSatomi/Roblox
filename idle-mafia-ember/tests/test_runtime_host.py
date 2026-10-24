"""Opt-in host owns subscriptions, timer and App shutdown together."""
import unittest

from engine_harness import Harness, lua_table


class RuntimeHostTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
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
                    files = deps.files,
                    shopQuoteSource = deps.shopQuoteSource,
                    rewardsSource = deps.rewardsSource,
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
            "NativeDispatchAdapter": self.h.load(
                "src/transport/NativeDispatchAdapter.luau"),
            "NativeRemoteResolver": self.h.load(
                "src/transport/NativeRemoteResolver.luau"),
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

    def test_events_tick_and_ui_unload_disconnect(self):
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        self.assertIsNotNone(host.app.transport.Send)
        self.assertIsNotNone(host.app.files.ReadFile)
        self.events.sync(lua_table(self.h.lua, {"cash": 10}))
        self.assertEqual(host.app.seen, 1)
        self.events.changed(lua_table(self.h.lua, {"cash": 11}))
        self.assertEqual(host.app.seen, 2)
        self.timer.callback()
        self.assertEqual(host.app.seen, 3)
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

    def test_current_client_mode_uses_resolved_bindings_and_observer(self):
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
        self.deps["activateCurrentClient"] = True
        self.deps["clientGame"] = self.h.lua.table()
        self.deps["clientRequire"] = self.h.lua.eval("function() end")
        self.deps["clientHash"] = self.h.lua.eval("function() end")
        self.deps["NativeClientBindings"] = self.h.lua.execute("""return {
            read = function() return {
                remotesFolder = real_folder, nativeState = real_state,
                currentDailyBuffRules = real_rewards_rule,
                config = { GROUP = { id = 123 }, COMBAT = { staminaCost = 2 } },
                gameData = { JOBS = { { id = 'j_watch' } } },
                gearSets = { slotBonus = function() end },
                combatRules = { staminaCost = 2 },
                groupLookup = function(id) return id == 123 end,
            } end,
        }""")
        self.deps["NativeRewardsSource"] = self.h.load(
            "src/tabs/rewards/NativeRewardsSource.luau")
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
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        self.assertIsNotNone(host)
        self.assertIsNotNone(self.events.sync)
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
        host.Destroy(host)

    def test_unbound_native_proof_sources_override_caller_values(self):
        self.deps["shopQuoteSource"] = self.h.lua.table_from({"fake": True})
        self.deps["rewardsSource"] = self.h.lua.table_from({"fake": True})
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(reason)
        self.assertIsNone(host.app.shopQuoteSource)
        self.assertIsNone(host.app.rewardsSource)
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

    def test_incompatible_client_never_starts_app_or_subscribes(self):
        self.observer["Read"] = self.h.lua.eval("""function()
            return { place = '73897506680154',
                account = 'user-a',
                gameVersion = '0.26.531',
                fingerprint = string.rep('a', 64) }
        end""")
        host, reason = self.host_module.start(self.deps)
        self.assertIsNone(host)
        self.assertEqual(reason, "Current client compatibility not verified")
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
        self.assertEqual(reason, "App startup failed")
        self.assertTrue(self.h.lua.globals().partial_app_destroyed)
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
        transport.Send(transport, proposal,
            self.h.lua.eval("function(_reply) end"),
            self.h.lua.eval("function() return true end"))
        self.deps["executorRuntimeApi"]["queued"][2]()
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


if __name__ == "__main__":
    unittest.main()
