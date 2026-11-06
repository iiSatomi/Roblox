"""The real tab/accounting/broker/native-dispatch order admits one bounded Favor."""
import unittest
from engine_harness import lua_table
import test_heist_runtime


class HeistAccountingCompositionTests(unittest.TestCase):
    setUp = test_heist_runtime.HeistRuntimeTests.setUp
    raw = test_heist_runtime.HeistRuntimeTests.raw
    def compose(self, feature='favors'):
        self.runtime.Close(self.runtime)
        paths = {
            'HeistRuntime':'tabs/heists/HeistRuntime', 'NativeHeistCatalog':'tabs/heists/NativeHeistCatalog',
            'BoardQuery':'tabs/heists/BoardQuery', 'BoardReadRuntime':'tabs/heists/BoardReadRuntime',
            'HeistBoardState':'game/HeistBoardState', 'HeistStart':'features/HeistStart',
            'HeistCollect':'features/HeistCollect', 'HeistCollectEvidence':'features/HeistCollectEvidence',
            'SabotageState':'game/SabotageState', 'Sabotage':'features/Sabotage',
            'FavorsState':'game/FavorsState', 'FavorHelp':'features/FavorHelp',
        }
        for name,path in paths.items(): self.deps[name]=self.h.load('src/'+path+'.luau')
        self.deps.gameData=lua_table(self.h.lua, {'HEISTS':[{'id':'h_a','level':10,'stake':10,
            'energy':2,'crateCount':1,'helpCash':100,'helpXp':5}]})
        heists=self.h.load('src/tabs/heists/Module.luau').new(self.deps)
        favors=self.h.load('src/tabs/favors/Module.luau').new(self.deps)
        composed,why=self.h.load('src/tabs/TabComposition.luau').build(
            lua_table(self.h.lua,[heists,favors]), self.h.load('src/ui/Catalog.luau'),
            self.h.load('src/engine/FeatureRegistry.luau'),self.h.load('src/tabs/TabSnapshotAssembler.luau'))
        self.assertIsNone(why)
        modules=lua_table(self.h.lua, {'Contracts':self.h.contracts,
            'heistRuntime':self.deps.heistRuntime,'PendingAction':self.deps.PendingAction,
            'HeistBoardState':self.deps.HeistBoardState})
        for name,folder in [('Broker','engine'),('Journal','engine'),('Context','game'),
                            ('Scheduler','engine'),('Session','engine'),('Checkpoint','storage')]:
            modules[name]=self.h.load('src/'+folder+'/'+name+'.luau')
        executor=self.h.lua.execute('''return {queued={}, rawCalls=0,
            Schedule=function(self,fn) self.queued[#self.queued+1]=fn end,
            Invoke=function(self) self.rawCalls=self.rawCalls+1; error('raw mutation forbidden') end,
            InvokeOwned=function(self) self.rawCalls=self.rawCalls+1; error('raw mutation forbidden') end,
            Drain=function(self) local q=self.queued;self.queued={};for _,fn in ipairs(q) do fn() end end}''')
        lane=self.h.load('src/engine/RequestLane.luau').new(self.h.clock)
        transport=self.h.load('src/transport/NativeDispatchAdapter.luau').new(
            self.deps.HeistCallPlan,executor,lane,self.h.clock,None,self.deps.nativeHeistController)
        runtime=self.h.load('src/engine/AutomationRuntime.luau').new(lua_table(self.h.lua,{
            'modules':modules,'features':composed.features,'featurePages':composed.featurePages,
            'snapshotAssembler':composed.snapshotAssembler,'clock':self.h.clock,
            'transport':transport,'storage':self.deps.storage,'identity':self.h.session}))
        raw=self.raw()
        raw.heistCatalog=None
        raw.native.pools.energy=20
        board=raw.heistBoardProof.board
        for key,value in {'favorsLeft':10,'helpFavorCost':1,'helpEnergyCost':2,
                          'helpMaxPerHeist':5,'helpCashCap':100,'saboFavorCost':2,
                          'saboEnergyCost':3,'saboMaxPerHeist':5}.items(): board[key]=value
        board.rows=lua_table(self.h.lua,[{'id':731,'heistId':'h_a','ownerId':99,
            'friend':feature=='favors','endsAt':1987400,'helpsUsed':0,'sabosUsed':0}])
        raw.localUserIdProof=lua_table(self.h.lua,{'account':'user-a','capturedAt':0,'userId':42})
        # Caller counts are stripped and replaced by the real checkpoint.
        raw.favorUsageProof=lua_table(self.h.lua,{'account':'user-a','day':23,'attempts':99,'capturedAt':0})
        settings=lua_table(self.h.lua,{feature:{'enabled':True,'policy':'Best reward',
            'maxDailyAttempts':1,'minFavorReserve':5,'minEnergyReserve':10,'relations':'Friends or Family'}})
        runtime.Resume(runtime)
        status=runtime.Step(runtime,raw,settings)
        usage=runtime.checkpoint.FavorUsage if feature=='favors' else runtime.checkpoint.SabotageUsage
        self.assertEqual(usage(runtime.checkpoint,23,0).attempts,1,
            (status.globalReason,dict(status.reasons.items())))
        self.composedRaw,self.composedSettings=raw,settings
        return runtime,executor

    def test_canonical_checkpoint_charge_does_not_block_its_own_favor_dispatch(self):
        runtime,executor=self.compose()
        executor.Drain(executor)
        self.assertEqual(len(self.client.heistCalls),1)
        self.assertEqual(self.client.heistCalls[1].action,'help')
        self.assertEqual(self.client.heistCalls[1].arg1,731)
        self.assertEqual(executor.rawCalls,0)
        self.assertIsNotNone(self.deps.heistRuntime.owner.Active(self.deps.heistRuntime.owner))

    def test_canonical_sabotage_charge_uses_same_owned_guard(self):
        runtime,executor=self.compose('sabotage')
        executor.Drain(executor)
        self.assertEqual(len(self.client.heistCalls),1)
        self.assertEqual(self.client.heistCalls[1].action,'sabotage')
        self.assertEqual(self.client.heistCalls[1].arg1,731)

    def test_one_favor_settles_exact_native_reply_and_new_board_then_cap_stops(self):
        runtime,executor=self.compose()
        executor.Drain(executor)
        self.client.finishHeist(lua_table(self.h.lua,{'ok':True,'cash':100,'xp':5}))
        after=self.h.lua.eval('''function(raw)
            local function clone(v) if type(v)~='table' then return v end
                local out={} for k,x in pairs(v) do out[k]=clone(x) end return out end
            return clone(raw)
        end''')(self.composedRaw)
        after.revision=2
        after.heistBoardProof.board.favorsLeft=9
        after.heistBoardProof.board.rows[1].helpsUsed=1
        after.native.pools.energy=18
        runtime.Step(runtime,after,self.composedSettings)
        self.assertEqual(len(runtime.checkpoint.Records(runtime.checkpoint)),0)
        self.assertIsNone(self.deps.heistRuntime.owner.Active(self.deps.heistRuntime.owner))
        self.assertTrue(self.deps.nativeHeistController.Read().controllersClear)
        self.assertEqual(runtime.checkpoint.FavorUsage(runtime.checkpoint,23,0).attempts,1)
        executor.Drain(executor)
        self.assertEqual(len(self.client.heistCalls),1)

    def test_changed_accounting_identity_or_charge_refuses_deferred_native_entry(self):
        for change in ('method','charge','record'):
            with self.subTest(change=change):
                self.setUp()
                runtime,executor=self.compose()
                self.assertFalse(self.deps.heistRuntime.BindAccounting(
                    self.deps.heistRuntime,self.h.lua.table()))
                if change=='method':
                    runtime.checkpoint.FavorUsage=self.h.lua.eval('function() return nil end')
                elif change=='charge':
                    runtime.checkpoint.favorUsage.attempts=2
                else:
                    runtime.checkpoint.records=self.h.lua.table()
                executor.Drain(executor)
                self.assertEqual(len(self.client.heistCalls),0)


if __name__=='__main__': unittest.main()
