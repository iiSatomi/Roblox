"""Resolve the live MWClient State and Remotes from current instances."""
import unittest

from engine_harness import Harness,lua_table


class NativeClientBindingsTests(unittest.TestCase):
    def test_native_territory_city_binding_uses_map_id_and_native_default_order(self):
        h,game,state,remotes,_,require,bindings,found = self.make_client()
        source = found.currentTerritoryCities
        self.assertIsNotNone(source)
        self.assertEqual(source.Select(source, None, "d_jade", lua_table(h.lua, {"level": 40}))[0].cityId, "jade_harbor")
        self.assertEqual(source.Select(source, None, None, lua_table(h.lua, {"level": 1}))[0].cityId, "vespera")
        self.assertEqual(source.Select(source, None, None, lua_table(h.lua, {"level": "40"}))[0].cityId, "jade_harbor")
        # Native ipairs order, not threshold sorting: an eligible later low-level city wins.
        cities = remotes.Parent.children.GameData.Value.CITIES
        cities[3] = lua_table(h.lua, {"id": "not-a-map-id", "name": "Vespera", "level": 2})
        self.assertEqual(source.Select(source, None, None, lua_table(h.lua, {"level": 40}))[0].cityId, "vespera")
        self.assertIsNone(source.Select(source, "city_jade", None, lua_table(h.lua, {"level": 40}))[0])
        self.assertEqual(source.Select(source, "jade_harbor", None, None)[0].cityId, "jade_harbor")

    def test_disabled_or_nil_city_maps_returns_explicit_nil_without_citymaps_module(self):
        for flag in (False, None):
            h,game,state,remotes,_,require,bindings,_ = self.make_client()
            remotes.Parent.children.Config.Value.TERRITORY.cityMaps = flag
            remotes.Parent.children.CityMaps = None
            source = bindings.read(game, require)[0].currentTerritoryCities
            self.assertIsNotNone(source)
            selected, why = source.Select(source, "jade_harbor", "d_jade", None)
            self.assertIsNone(why)
            self.assertIsNotNone(selected)
            self.assertIsNone(selected.cityId)

    def test_missing_named_mapping_and_replaced_native_sources_do_not_guess(self):
        for change in ("missing", "module", "names", "config"):
            with self.subTest(change=change):
                h,game,state,remotes,_,_,_,found = self.make_client()
                source = found.currentTerritoryCities
                self.assertIsNotNone(source)
                mw = remotes.Parent
                if change == "missing": mw.children.CityMaps.Value.BY_NAME["Jade Harbor"] = None
                elif change == "module": mw.children.CityMaps.Parent = None
                elif change == "names": mw.children.CityMaps.Value.BY_NAME = h.lua.table()
                else: mw.children.Config.Value.TERRITORY = lua_table(h.lua, {"cityMaps": True})
                self.assertIsNone(source.Select(source, None, "d_jade", lua_table(h.lua, {"level": 40}))[0])

    def make_client(self):
        h = Harness()
        game, state, remotes, state_module = h.lua.execute("""
            local function node(name, class)
                local value = { Name = name, ClassName = class, children = {} }
                function value:IsA(kind) return self.ClassName == kind end
                function value:FindFirstChild(key) return self.children[key] end
                function value:GetChildren() local rows={};for _,v in pairs(self.children) do rows[#rows+1]=v end;return rows end
                function value:GetAttribute(key) return self.attributes and self.attributes[key] end
                function value:Add(child)
                    self.children[child.Name] = child
                    child.Parent = self
                    return child
                end
                return value
            end
            local replicated = node('ReplicatedStorage', 'ReplicatedStorage')
            local remotes = replicated:Add(node('MW', 'Folder'))
                :Add(node('Remotes', 'Folder'))
            remotes:Add(node('Sync', 'RemoteEvent'))
            remotes:Add(node('Attack','RemoteFunction'))
            remotes:Add(node('Notify','RemoteEvent')).OnClientEvent={
                Connect=function(self,cb) self.callback=cb;return {Disconnect=function() self.callback=nil end} end}
            local mw = remotes.Parent
            mw.attributes = {GlobalBossState='public-event',
                GlobalEventShop=true,GlobalEventShopEnd=2000}
            mw:Add(node('EventShop', 'ModuleScript')).Value = {
                MEDAL='event_medal',MAX_ITEM_COUNT=99,ROWS={
                    {key='gold',kind='item',item='gold_bar',price=3,count=1}}}
            mw.attributes.SeasonLive='season-json'
            mw:Add(node('SeasonRules','ModuleScript')).Value = {
                status=function(live, now) return {phase='running',n=live and live.season or 1,
                    startsAt=900,endsAt=2000} end}
            mw:Add(node('GlobalBossRules', 'ModuleScript')).Value = {
                ATTR='GlobalBossState',PRIVATE_ATTR='GlobalBossPrivateState',
                decode=function() return nil end,canAccess=function() return true end}
            mw:Add(node('DailyBuffRules', 'ModuleScript')).Value = {
                isWeekend = function() return true end }
            mw:Add(node('Config', 'ModuleScript')).Value = {
                GROUP = { id = 123 }, COMBAT = { staminaCost = 2 }, TERRITORY = {cityMaps=true} }
            mw:Add(node('GameData', 'ModuleScript')).Value = {
                CITIES = {{id='city_vespera',name='Vespera',level=1},{id='city_jade',name='Jade Harbor',level=30}},
                DISTRICTS_BY_ID = {d1={city='Vespera'},d_jade={city='Jade Harbor'}},
                JOBS = { { id = 'j_watch' } },
                SHOP = { { item = 'w_bat' } },
                ITEMS_BY_ID = { w_bat = { kind = 'weapon' } } }
            local firstCity, jadeCity = {id='vespera',name='Vespera'}, {id='jade_harbor',name='Jade Harbor'}
            mw:Add(node('CityMaps','ModuleScript')).Value = {CITIES={firstCity,jadeCity},
                BY_NAME={Vespera=firstCity,['Jade Harbor']=jadeCity}}
            mw:Add(node('GearSets', 'ModuleScript')).Value = {
                slotBonus = function() end }
            mw:Add(node('Util', 'ModuleScript')).Value = {
                shopStock = function() end,
                shopPrice = function() end }
            mw:Add(node('TerritoryBonusRules', 'ModuleScript')).Value = {
                fromData = function(native, key) if key == "crateLuck" then return native.luckBonus end end,
                shopPrice = function() end,
                crateLuck = function(native) return native.luckBonus end }
            mw:Add(node('GlobalBuffKinds', 'ModuleScript')).Value = {
                sale = function() end, luck = function() return 0 end }
            mw:Add(node('DecreeRules', 'ModuleScript')).Value = {
                pctFor = function() end }
            mw:Add(node('ServerClock', 'ModuleScript')).Value = {
                now = function() return 0 end }
            mw:Add(node('BossStages', 'ModuleScript')).Value = {
                MAX_STAGE = 100000,
                get = function() end,
                crateUnlocked = function() return false end,
                SHOP = { gear = {}, crates = {} } }
            local scripts = node('PlayerScripts', 'PlayerScripts')
            local stateModule = scripts:Add(node('MWClient', 'LocalScript'))
                :Add(node('State', 'ModuleScript'))
            local state = { data = { cash = 10 }, lastSyncClock = 5,
                latest = function() return { cash = 10 } end,
                onChanged = function() return { Disconnect = function() end } end }
            stateModule.Value = state
            local wrappers={}
            stateModule.Parent:Add(node('RemoteLink','ModuleScript')).Value={wrap=function(folder)
                return {FindFirstChild=function(_,name)
                    local raw=folder:FindFirstChild(name)
                    if not raw or not raw:IsA('RemoteFunction') then return raw end
                    if not wrappers[raw] then wrappers[raw]={Name=name,Instance=raw,
                        InvokeServer=function(_,...) return raw:InvokeServer('fixture-native-header',...) end} end
                    return wrappers[raw]
                end}
            end}
            local presence = {blocked=false,opened={}}
            function presence.pending(domain) assert(domain=='market'); return presence.blocked end
            function presence.open(payload,domain) presence.opened[#presence.opened+1]={payload=payload,domain=domain} end
            stateModule.Parent:Add(node('TerritoryPresence','ModuleScript')).Value=presence

            local player = node('user-a', 'Player')
            player.UserId=42
            player.OnTeleport={Connect=function() return {Disconnect=function() end} end}
            player.attributes={GlobalBossPrivateState='private-event'}
            function player:IsInGroup(id) return id == 123 end
            player:Add(scripts)
            local players = { LocalPlayer = player }
            local game = {}
            function game:GetService(name)
                if name == 'Players' then return players end
                if name == 'ReplicatedStorage' then return replicated end
                if name == 'HttpService' then return {JSONDecode=function(_, value)
                    if value=='season-json' then return {season=2,startsAt=900,endsAt=2000} end
                    error('malformed') end} end
            end
            return game, state, remotes, stateModule
        """)
        require = h.lua.eval("function(module) return module.Value end")
        bindings = h.load("src/transport/NativeClientBindings.luau")
        found, reason = bindings.read(game, require)
        self.assertIsNone(reason)
        self.assertTrue(h.lua.eval('function(a,b)return a==b end')(found.teleportSignal, game.GetService(game,'Players').LocalPlayer.OnTeleport))
        return h,game,state,remotes,state_module,require,bindings,found

    def test_current_instance_paths_and_state_api(self):
        h,game,state,remotes,state_module,require,bindings,found=self.make_client()
        self.assertFalse(found.currentFightNotifications.CanAttack(found.currentFightNotifications,h.lua.table(),99)[0])
        notifications=found.currentFightNotifications
        self.assertIsNotNone(notifications);self.assertTrue(notifications.Current())
        notify=remotes.children.Notify;handle=notifications.Subscribe(notifications,h.lua.eval("function() end"))
        handle.Disconnect(handle);remotes.children.Notify=None
        self.assertFalse(notifications.Current())
        with self.assertRaises(Exception): notifications.Subscribe(notifications,h.lua.eval("function() end"))
        remotes.children.Notify=notify
        native_link=found.nativeRemoteLink
        self.assertIsNotNone(native_link);self.assertTrue(native_link.Current())
        link_module=state_module.Parent.children.RemoteLink;state_module.Parent.children.RemoteLink=None
        self.assertFalse(native_link.Current())
        with self.assertRaises(Exception): native_link.Resolve(native_link,'Attack')
        game.PlaceVersion=648
        self.assertIsNone(bindings.read(game,require)[0])
        game.PlaceVersion=None
        state_module.Parent.children.RemoteLink=link_module
        presence_module = state_module.Parent.children.TerritoryPresence
        presence = presence_module.Value
        self.assertTrue(found.marketPresence.check()[0])
        presence.blocked = True
        self.assertFalse(found.marketPresence.check()[0])
        self.assertEqual(presence.opened[1].domain, "market")
        self.assertFalse(found.marketPresence.check()[0])
        self.assertEqual(len(presence.opened), 1)
        presence.blocked = False
        payload = h.lua.table()
        reply = h.lua.table(code="presence", presence=payload)
        self.assertFalse(found.marketPresence.handle(reply)[0])
        self.assertEqual(presence.opened[2].domain, "market")
        original_pending = presence.pending
        presence.pending = h.lua.eval("function() return false end")
        self.assertFalse(found.marketPresence.check()[0])
        presence.pending = original_pending

        same = h.lua.eval("function(a, b) return a == b end")
        self.assertTrue(same(found.remotesFolder, remotes))
        self.assertTrue(same(found.nativeState, state))
        self.assertIsNotNone(found.currentDailyBuffRules)
        self.assertEqual(found.config.GROUP.id, 123)
        self.assertEqual(found.gameData.JOBS[1].id, 'j_watch')
        self.assertIsNotNone(found.gearSets.slotBonus)
        self.assertEqual(found.combatRules.staminaCost, 2)
        self.assertIsNotNone(found.currentShop)
        self.assertIsNotNone(found.currentCrateLuck)
        self.assertIsNotNone(found.bossStages)
        self.assertEqual(found.currentGlobalBoss.userId, 42)
        attributes = found.currentGlobalBoss.readAttributes()
        self.assertEqual(attributes.GlobalBossState, 'public-event')
        self.assertEqual(attributes.GlobalBossPrivateState, 'private-event')
        season = found.currentTerritorySeason
        self.assertIsNotNone(season)
        self.assertEqual(season.readLive().season, 2)
        self.assertEqual(season.status(season.readLive(), 1000).n, 2)
        remotes.Parent.attributes.SeasonLive = 'malformed'
        self.assertIsNone(season.readLive())
        remotes.Parent.attributes.SeasonLive = None
        self.assertIsNone(season.readLive())
        season_module = remotes.Parent.children.SeasonRules
        remotes.Parent.children.SeasonRules = None
        with self.assertRaises(Exception):
            season.readLive()
        remotes.Parent.children.SeasonRules = season_module
        shop = found.currentEventShop
        self.assertIsNotNone(shop)
        self.assertEqual(shop.definition.ROWS[1].key, 'gold')
        shop_attributes = shop.readAttributes()
        self.assertTrue(shop_attributes.GlobalEventShop)
        self.assertEqual(shop_attributes.GlobalEventShopEnd, 2000)
        self.assertIsNone(shop_attributes.MWPaidRandomRestricted)
        clock_rule = remotes.Parent.children.ServerClock.Value
        original_now = clock_rule.now
        clock_rule.now = h.lua.eval('function() return nil end')
        with self.assertRaises(Exception):
            shop.readAttributes()
        clock_rule.now = original_now
        remotes.Parent.attributes.GlobalEventShop = False
        self.assertFalse(shop.readAttributes().GlobalEventShop)
        shop_module = remotes.Parent.children.EventShop
        remotes.Parent.children.EventShop = None
        with self.assertRaises(Exception):
            shop.readAttributes()
        missing_shop, _ = bindings.read(game, require)
        self.assertIsNone(missing_shop.currentEventShop)
        remotes.Parent.children.EventShop = shop_module
        h.lua.globals().bindingGame = game
        h.lua.execute("bindingGame:GetService('Players').LocalPlayer={}")
        with self.assertRaises(Exception):
            shop.readAttributes()
        h.lua.execute("bindingGame:GetService('Players').LocalPlayer=nil")
        # Restore the original player for the remaining independent checks.
        h.lua.globals().bindingPlayerScripts = state_module.Parent.Parent
        h.lua.execute("bindingGame:GetService('Players').LocalPlayer=bindingPlayerScripts.Parent")
        self.assertEqual(found.currentCrateLuck.crateLuck(
            h.lua.table_from({"luckBonus": 0.4})), 0.4)
        self.assertTrue(same(found.currentShop.mw, remotes.Parent))
        source = h.load("src/tabs/shop/NativeQuoteSource.luau")
        quote, quote_reason = source.new(found.currentShop,
            "release-a", "a" * 64)
        self.assertIsNone(quote_reason)
        self.assertIsNotNone(quote)
        self.assertTrue(found.groupLookup(123))
        self.assertFalse(found.groupLookup(124))
        remotes.Parent.children["GlobalBuffKinds"] = None
        missing, missing_reason = bindings.read(game, require)
        self.assertIsNone(missing_reason)
        self.assertIsNone(missing.currentShop)
        state_module.Parent = None
        self.assertIsNone(bindings.read(game, require)[0])


    def fight_client(self):
        h,game,state,remotes,sm,require,bindings,_=self.make_client()
        h.lua.globals().guardGame=game;h.lua.globals().guardState=state
        h.lua.globals().guardFolder=remotes;h.lua.globals().guardClient=sm.Parent
        probe=h.lua.execute("""local p={busy=false,family=false,warning=nil,shield=0,gap=0,remaining=5,cooldown=0}
            guardGame.PlaceVersion=648
            local cfg=guardFolder.Parent.children.Config.Value
            cfg.COMBAT={staminaCost=2,hospitalHealth=20,bullyMaxStamina=5}
            guardState.data.stats={maxHealth=100}
            guardState.data.pools={health=80,stamina=6};guardState.data.shieldUntil=0;guardState.data.serverNow=1000
            guardState.latest=function() return guardState.data end
            local attackRemote={Name='Attack',Parent=guardFolder,IsA=function(_,kind) return kind=='RemoteFunction' end}
            guardFolder.children.Attack=attackRemote
            local nativeLink=guardClient.children.RemoteLink.Value.wrap(guardFolder)
            local ctx={State=guardState,Config=cfg,Remotes={Attack=nativeLink:FindFirstChild('Attack')}}
            local blocked=function() end;local perform=function() end
            local family=function() return p.family end
            local war={warning=function() return p.warning end}
            local attack=function() end
            local f={attack=attack,cooldownLeft=function() return p.cooldown end,attacksRemaining=function() return p.remaining end}
            guardClient.children.FightTab={Parent=guardClient,Name='FightTab',Value=f,IsA=function(_,kind) return kind=='ModuleScript' end}
            p.upvalues=function(fn)
                if fn==attack then return {blocked,ctx,family,p.shield,war,function() end,perform} end
                if fn==blocked then return {p.busy,ctx,function() end,{},p.gap} end
                if fn==perform then return {[14]=function(_,_,reply) p.feedback=(p.feedback or 0)+1;if p.mutateFeedback then reply.ok=true end end} end
                error('Unknown native function')
            end
            return p""")
        found,why=bindings.read(game,require,probe.upvalues);self.assertIsNone(why)
        proposal=h.lua.table(feature='combat',intent=h.lua.table(kind='playerAttack',target=99,familyId='other',shieldUntil=0,expectedStaminaCost=2,maxStaminaExposure=5,staminaReserve=1,uncertainStamina=0,healthFloor=50),resources=h.lua.table(stamina=5))
        return h,game,state,probe,found.currentFightNotifications,proposal

    def scout_client(self):
        h,game,state,p,source,proposal=self.fight_client()
        client=h.lua.globals().guardClient
        h.lua.globals().scoutProbe=p
        h.lua.execute("""local p=scoutProbe;local client=guardClient;local cfg=guardFolder.Parent.children.Config.Value
            cfg.COMBAT.scoutStaminaCost=1
            local raw={Name='ScoutPlayer',Parent=guardFolder,IsA=function(_,k) return k=='RemoteFunction' end}
            guardFolder.children.ScoutPlayer=raw
            local ctx={State=guardState,Config=cfg,Remotes={ScoutPlayer=client.children.RemoteLink.Value.wrap(guardFolder):FindFirstChild('ScoutPlayer')}}
            local open=function() end;p.profileOpen=open;p.profileCtx=ctx;p.profileBusy=false
            client.children.ProfilePopup={Name='ProfilePopup',Parent=client,Value={open=open},IsA=function(_,k) return k=='ModuleScript' end}
            local old=p.upvalues
            p.upvalues=function(fn) if fn==open then return {[1]=0,[3]=p.profileBusy,[5]=ctx} end;return old(fn) end
        """)
        bindings=h.load('src/transport/NativeClientBindings.luau')
        require=h.lua.eval('function(m) return m.Value end')
        found,why=bindings.read(game,require,p.upvalues);self.assertIsNone(why)
        proposal.intent.kind='playerScout';proposal.intent.expectedStaminaCost=1
        proposal.intent.attackExposure=5;proposal.intent.allowScout=True
        state.data.pools.stamina=11
        return h,game,state,p,found.currentFightNotifications,proposal

    def test_verified_builds_support_attack_and_scout_without_cross_build_reuse(self):
        for version in (648, 653, 654, 655):
            for scout in (False, True):
                h,game,state,p,_,proposal=self.scout_client() if scout else self.fight_client()
                game.PlaceVersion=version
                found,why=h.load('src/transport/NativeClientBindings.luau').read(
                    game,h.lua.eval('function(m) return m.Value end'),p.upvalues)
                self.assertIsNone(why)
                source=found.currentFightNotifications
                guard=source.CanScout if scout else source.CanAttack
                self.assertTrue(guard(source,proposal,99)[0])
                game.PlaceVersion=653 if version==648 else 648
                self.assertFalse(guard(source,proposal,99)[0])
                game.PlaceVersion=version
                self.assertFalse(guard(source,proposal,99)[0])

    def test_build_transition_inside_native_state_callback_refuses_guard_result(self):
        for scout in (False, True):
            h,game,state,p,_,proposal=self.scout_client() if scout else self.fight_client()
            game.PlaceVersion=653
            found,_=h.load('src/transport/NativeClientBindings.luau').read(
                game,h.lua.eval('function(m) return m.Value end'),p.upvalues)
            source=found.currentFightNotifications
            state.latest=h.lua.eval('function() guardGame.PlaceVersion=648;return guardState.data end')
            guard=source.CanScout if scout else source.CanAttack
            self.assertFalse(guard(source,proposal,99)[0])

    def test_unknown_builds_and_missing_upvalue_reader_never_enable_attack(self):
        for version in (647, 649, 652, 656, '653'):
            h,game,state,p,_,proposal=self.fight_client()
            game.PlaceVersion=version
            found,_=h.load('src/transport/NativeClientBindings.luau').read(
                game,h.lua.eval('function(m) return m.Value end'),p.upvalues)
            self.assertFalse(found.currentFightNotifications.CanAttack(found.currentFightNotifications,proposal,99)[0])
        game.PlaceVersion=653
        found,_=h.load('src/transport/NativeClientBindings.luau').read(game,h.lua.eval('function(m) return m.Value end'))
        self.assertFalse(found.currentFightNotifications.CanAttack(found.currentFightNotifications,proposal,99)[0])

    def test_build_change_during_initial_or_lazy_requires_cannot_be_recaptured(self):
        for version,changed in ((648,653),(653,648),(654,653)):
            for module in ('State','FightTab','ProfilePopup'):
                h,game,state,p,_,proposal=self.scout_client()
                game.PlaceVersion=version
                require=h.lua.eval("function(m) if m.Name=='"+module+"' then guardGame.PlaceVersion="+str(changed)+" end;return m.Value end")
                found,why=h.load('src/transport/NativeClientBindings.luau').read(game,require,p.upvalues)
                self.assertIsNotNone(found,why)
                self.assertFalse(found.currentFightNotifications.CanScout(found.currentFightNotifications,proposal,99)[0])

    def test_build_653_still_checks_busy_context_and_module_identity(self):
        h,game,state,p,_,proposal=self.fight_client();game.PlaceVersion=653
        found,_=h.load('src/transport/NativeClientBindings.luau').read(
            game,h.lua.eval('function(m) return m.Value end'),p.upvalues)
        source=found.currentFightNotifications
        self.assertTrue(source.CanAttack(source,proposal,99)[0])
        p.busy=True;self.assertFalse(source.CanAttack(source,proposal,99)[0]);p.busy=False
        h.lua.globals().guardClient.children.FightTab.Value.attack=h.lua.eval('function() end')
        self.assertFalse(source.CanAttack(source,proposal,99)[0])

    def test_native_scout_guard_requires_optin_exact_cost_and_followup_reserve(self):
        h,game,state,p,source,proposal=self.scout_client()
        self.assertIsNotNone(source.CanScout)
        self.assertTrue(source.CanScout(source,proposal,99)[0])
        for key,value in (('allowScout',False),('expectedStaminaCost',2),('attackExposure',4),('maxStaminaExposure',1)):
            with self.subTest(key=key):
                old=proposal.intent[key];proposal.intent[key]=value
                self.assertFalse(source.CanScout(source,proposal,99)[0]);proposal.intent[key]=old
        state.data.pools.stamina=10;self.assertFalse(source.CanScout(source,proposal,99)[0])
        state.data.pools.stamina=12;proposal.intent.uncertainStamina=2
        self.assertFalse(source.CanScout(source,proposal,99)[0])
        proposal.intent.uncertainStamina=0;proposal.feature='warCombat'
        self.assertFalse(source.CanScout(source,proposal,99)[0])

    def test_native_scout_guard_honors_busy_context_and_source_replacement(self):
        h,game,state,p,source,proposal=self.scout_client()
        self.assertIsNotNone(source.CanScout)
        self.assertTrue(source.CanScout(source,proposal,99)[0])
        for key,value in (('profileBusy',True),('busy',True),('family',True),('warning','manual warning'),('remaining',0)):
            old=p[key];p[key]=value
            self.assertFalse(source.CanScout(source,proposal,99)[0]);p[key]=old
        p.profileCtx.Remotes.ScoutPlayer=h.lua.table()
        self.assertFalse(source.CanScout(source,proposal,99)[0])
        h,game,state,p,source,proposal=self.scout_client()
        self.assertTrue(source.CanScout(source,proposal,99)[0])
        h.lua.globals().guardClient.children.ProfilePopup.Value.open=h.lua.eval('function() end')
        self.assertFalse(source.CanScout(source,proposal,99)[0])
        game.PlaceVersion=649;self.assertFalse(source.CanScout(source,proposal,99)[0])

    def test_scout_guard_rechecks_after_native_require_and_checks_wrapper_instance(self):
        h,game,state,p,source,proposal=self.scout_client()
        self.assertTrue(source.CanScout(source,proposal,99)[0])
        p.profileCtx.Remotes.ScoutPlayer.Instance=h.lua.table()
        self.assertFalse(source.CanScout(source,proposal,99)[0])
        h,game,state,p,source,proposal=self.scout_client()
        h.lua.globals().changingProbe=p
        require=h.lua.eval("function(m) if m.Name=='ProfilePopup' then changingProbe.busy=true;guardState.data.pools.health=0 end;return m.Value end")
        found=h.load('src/transport/NativeClientBindings.luau').read(game,require,p.upvalues)[0]
        self.assertFalse(found.currentFightNotifications.CanScout(found.currentFightNotifications,proposal,99)[0])

    def test_current_native_attack_preflight_blocks_busy_resources_and_limits(self):
        h,game,state,p,source,proposal=self.fight_client()
        self.assertTrue(source.CanAttack(source,proposal,99)[0])
        for key,value in (("busy",True),("family",True),("warning","Native war warning"),("shield",9999999999),("gap",9999999999),("remaining",0),("cooldown",1)):
            with self.subTest(key=key):
                old=p[key];p[key]=value;self.assertFalse(source.CanAttack(source,proposal,99)[0]);p[key]=old
        for key,value in (("health",19),("stamina",1)):
            old=state.data.pools[key];state.data.pools[key]=value
            self.assertFalse(source.CanAttack(source,proposal,99)[0]);state.data.pools[key]=old

    def test_native_attack_preflight_requires_known_version_exact_cost_and_player_mode(self):
        h,game,state,p,source,proposal=self.fight_client()
        game.PlaceVersion=649;self.assertFalse(source.CanAttack(source,proposal,99)[0]);game.PlaceVersion=648
        proposal.resources.stamina=1;self.assertFalse(source.CanAttack(source,proposal,99)[0]);proposal.resources.stamina=5
        proposal.feature='warCombat';self.assertFalse(source.CanAttack(source,proposal,99)[0]);proposal.feature='combat'
        self.assertFalse(source.CanAttack(source,proposal,42)[0])
        proposal.intent.target=98;self.assertFalse(source.CanAttack(source,proposal,99)[0])

    def test_owned_failure_uses_native_feedback_without_handling_other_successes(self):
        h,game,state,p,source,proposal=self.fight_client()
        self.assertTrue(source.HandleReply(source,h.lua.table(ok=False,code='target_hospitalized',msg='Native message')))
        self.assertEqual(p.feedback,1)
        self.assertTrue(source.HandleReply(source,h.lua.table(ok=True)))
        self.assertEqual(p.feedback,1)

    def test_native_feedback_cannot_change_the_owned_initial_result(self):
        h,game,state,p,source,proposal=self.fight_client()
        p.mutateFeedback=True;reply=h.lua.table(ok=False,code='target_hospitalized')
        self.assertTrue(source.HandleReply(source,reply));self.assertFalse(reply.ok)


    def test_friendship_api_is_pinned_failure_unknown_and_post_yield_scope_checked(self):
        h,game,state,remotes,state_module,require,bindings,found=self.make_client()
        player=game.GetService(game,'Players').LocalPlayer
        player.IsFriendsWithAsync=h.lua.eval('function(self,id) self.friendCalls=(self.friendCalls or 0)+1;return id==99 end')
        found,why=bindings.read(game,require);self.assertIsNone(why);source=found.currentFightNotifications
        self.assertTrue(source.Friendship(source,99));self.assertFalse(source.Friendship(source,98))
        self.assertEqual(player.friendCalls,2)
        player.IsFriendsWithAsync=h.lua.eval('function() error("lookup failed") end')
        self.assertIsNone(source.Friendship(source,99))
        found,why=bindings.read(game,require);source=found.currentFightNotifications
        self.assertIsNone(source.Friendship(source,99))
        h.lua.globals().friendNotify=remotes.children.Notify;h.lua.globals().friendRemotes=remotes
        player.IsFriendsWithAsync=h.lua.eval('function() friendRemotes.children.Notify=nil;return false end')
        found,why=bindings.read(game,require);source=found.currentFightNotifications
        self.assertIsNone(source.Friendship(source,99))


    def test_attack_guard_requires_configured_maximum_exposure_and_frozen_reserves(self):
        h,game,state,p,source,proposal=self.fight_client()
        proposal.intent.maxStaminaExposure=None
        self.assertFalse(source.CanAttack(source,proposal,99)[0])
        cfg=game.GetService(game,'ReplicatedStorage').children.MW.children.Config.Value
        cfg.COMBAT.bullyMaxStamina=5;state.data.stats=h.lua.table(maxHealth=100)
        state.data.pools.stamina=6
        proposal.resources.stamina=5;proposal.intent.expectedStaminaCost=2;proposal.intent.maxStaminaExposure=5
        proposal.intent.staminaReserve=1;proposal.intent.uncertainStamina=0;proposal.intent.healthFloor=50
        self.assertTrue(source.CanAttack(source,proposal,99)[0])
        state.data.pools.stamina=5;self.assertFalse(source.CanAttack(source,proposal,99)[0])
        state.data.pools.stamina=10;proposal.intent.uncertainStamina=5
        self.assertFalse(source.CanAttack(source,proposal,99)[0])
        proposal.intent.uncertainStamina=0;state.data.pools.health=49
        self.assertFalse(source.CanAttack(source,proposal,99)[0])

    def test_player_info_build_653_reads_verified_path_and_retires_cross_build_source(self):
        h,game,state,remotes,sm,require,bindings,_=self.make_client()
        game.PlaceVersion=653
        cfg=remotes.Parent.children.Config.Value
        cfg.fightIncomeMult=h.lua.eval('function(raid,streak,now) assert(now==1000.5);return 1.5 end')
        remotes.Parent.children.GameData.Value.PROPERTIES=lua_table(h.lua,[{'id':'p_a','name':'Diner','incomePerHour':100}])
        found,why=bindings.read(game,require);self.assertIsNone(why)
        source=found.currentPlayerInfo
        native=lua_table(h.lua,{'userId':42,'serverNow':1000.5})
        facts=source.Read(source,native);self.assertIsNotNone(facts)
        self.assertEqual(facts.propertyMultiplier,1.5);self.assertEqual(facts.properties[1].incomePerHour,100)
        game.PlaceVersion=648;self.assertFalse(source.Current());self.assertIsNone(source.Read(source,native))
        game.PlaceVersion=653;self.assertFalse(source.Current());self.assertIsNone(source.Read(source,native))

    def test_player_info_unknown_builds_and_changes_during_initial_require_refuse(self):
        for version in (647,649,652,656,'653'):
            h,game,state,remotes,sm,require,bindings,_=self.make_client();game.PlaceVersion=version
            found,_=bindings.read(game,require)
            self.assertFalse(found.currentPlayerInfo.Current())
            self.assertIsNone(found.currentPlayerInfo.Read(found.currentPlayerInfo,lua_table(h.lua,{'userId':42,'serverNow':1000})))
        for version,changed in ((648,653),(653,648),(654,653)):
            h,game,state,remotes,sm,require,bindings,_=self.make_client();game.PlaceVersion=version
            h.lua.globals().infoGame=game
            require=h.lua.eval('function(m) if m.Name=="State" then infoGame.PlaceVersion='+str(changed)+' end;return m.Value end')
            found,_=bindings.read(game,require)
            self.assertFalse(found.currentPlayerInfo.Current())

    def test_player_info_build_change_inside_income_helper_refuses_result(self):
        for version,changed in ((648,653),(653,648),(654,653)):
            h,game,state,remotes,sm,require,bindings,_=self.make_client();game.PlaceVersion=version
            h.lua.globals().infoGame=game
            remotes.Parent.children.Config.Value.fightIncomeMult=h.lua.eval(
                'function() infoGame.PlaceVersion='+str(changed)+';return 1.5 end')
            found,_=bindings.read(game,require);source=found.currentPlayerInfo
            self.assertTrue(source.Current())
            self.assertIsNone(source.Read(source,lua_table(h.lua,{'userId':42,'serverNow':1000})))
            game.PlaceVersion=version;self.assertFalse(source.Current())

    def test_player_info_native_source_uses_exact_fight_income_helper_and_current_identity(self):
        h,game,state,remotes,sm,require,bindings,found=self.make_client()
        game.PlaceVersion=648
        cfg=remotes.Parent.children.Config.Value
        cfg.fightIncomeMult=h.lua.eval('function(raid,streak,now) assert(raid==nil and streak==nil and now==1000.5);return 1.5 end')
        h.lua.globals().propertyData=remotes.Parent.children.GameData.Value
        h.lua.execute("propertyData.PROPERTIES={{id='p_a',name='Diner',incomePerHour=100},{id='p_gold',name='Gold business',goldPerDay=1}}")
        found,why=bindings.read(game,require);self.assertIsNone(why)
        source=found.currentPlayerInfo;self.assertIsNotNone(source)
        native=lua_table(h.lua,{'userId':42,'serverNow':1000.5})
        facts=source.Read(source,native);self.assertEqual(facts.propertyMultiplier,1.5)
        self.assertEqual(facts.properties[1].name,'Diner');self.assertEqual(facts.userId,42)
        self.assertEqual(facts.properties[2].incomePerHour,0)
        native.userId=99;self.assertIsNone(source.Read(source,native));native.userId=42
        module=remotes.Parent.children.GameData;remotes.Parent.children.GameData=None
        self.assertFalse(source.Current());self.assertIsNone(source.Read(source,native))
        remotes.Parent.children.GameData=module
        cfg.fightIncomeMult=h.lua.eval('function() return 99 end');self.assertIsNone(source.Read(source,native))

if __name__ == "__main__":
    unittest.main()
