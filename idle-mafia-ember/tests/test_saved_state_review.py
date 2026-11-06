"""Explicit inert App review with real strict disk envelopes; no migration or writes."""
import hashlib
import json
import unittest
from types import SimpleNamespace
from pathlib import Path
from lupa import lua_type
import test_ui_prototype as ui_fixture
from test_redundant_store import plain

ROOT=Path(__file__).resolve().parents[1]

class SavedStateReviewTests(unittest.TestCase):
    def setUp(self):
        self.f=ui_fixture.PrototypeTests(); self.f.setUp(); self.lua=self.f.lua
        self.disk={}; self.reads=[]; self.listings=[]; self.writes=[]
        self.fail_path=None; self.close_on_read=False; self.reenter=False; self.changed=None; self.list_override=None
        g=self.lua.globals()
        def read(path):
            self.reads.append(path)
            if self.close_on_read: self.app.Destroy(self.app)
            if self.reenter:
                self.reenter=False
                self.assertFalse(self.app.ReviewSavedState(self.app))
            if path==self.fail_path: raise OSError("PRIVATE ERROR TOKEN")
            value=self.disk.get(path)
            if self.changed and path==self.changed and self.reads.count(path)>1:
                return (value or "")+" "
            return value
        def listing(path):
            self.listings.append(path)
            if self.list_override is not None: return self.f.table(self.list_override)
            return self.f.table(sorted(p for p in self.disk if p.startswith(path+"/")))
        g.reviewRead=read; g.reviewExists=lambda path:path in self.disk
        g.reviewList=listing; g.reviewWrite=lambda path,text:self.writes.append((path,text))
        g.reviewEncode=lambda value:json.dumps(plain(value),sort_keys=True,separators=(",",":"))
        g.reviewDecode=lambda text:self.f.table(json.loads(text))
        g.reviewHash=lambda text:hashlib.sha256(text.encode()).hexdigest()
        self.env=self.lua.eval("""{isfile=function(p) return reviewExists(p) end,
            readfile=function(p) return reviewRead(p) end,listfiles=function(p) return reviewList(p) end,
            writefile=function(p,v) return reviewWrite(p,v) end,makefolder=function(p) error('mkdir') end,
            isfolder=function() return true end}""")
        self.http=self.lua.eval("""{JSONEncode=function(_,v) return reviewEncode(v) end,
            JSONDecode=function(_,v) return reviewDecode(v) end}""")
        self.deps=self.f.table({"identity":{"account":"user-a","place":"73897506680154","release":"current"},
            "directory":"IdleMafiaEmber","executorEnv":self.env,"httpService":self.http})
        self.deps.sha256=self.lua.eval("function(v) return reviewHash(v) end")
        self.deps.ExecutorStorageAdapter=self.f.module('src/storage/ExecutorStorageAdapter.luau')
        self.deps.RedundantStore=self.f.module('src/storage/RedundantStore.luau')
        self.deps.SavedStateReview=self.f.module('src/storage/SavedStateReview.luau')
        original=self.f.module
        def module(name):
            loaded=original(name)
            if name!='src/App.luau': return loaded
            def start(deps):
                for key,value in self.deps.items(): deps[key]=value
                self.fixture_deps=deps
                return loaded.start(deps)
            return SimpleNamespace(start=start)
        self.f.module=module
        self.app,self.ember=self.f.app()
        self.button=next(h for h in self.app.ui.window.handles.values()
            if h.kind=='Button' and h.options.Text=='Review saved state')
        self.legacy='IdleMafiaFluent/73897506680154/user-a/'
        self.before=dict(self.disk)

    def save(self,name,value): self.disk[self.legacy+name+'.json']=json.dumps(value)
    def click(self):
        self.button.Click(self.button); self.ember.Flush()
        return self.app.savedStateReview
    def report_text(self):
        return json.dumps(plain(self.app.savedStateReview),sort_keys=True)
    def store(self):
        files=self.lua.eval("""{ReadFile=function(_,p) return reviewRead(p) end,
            WriteFile=function(_,p,v) producerDisk(p,v);return true end}""")
        self.lua.globals().producerDisk=lambda path,text:self.disk.__setitem__(path,text)
        codec=self.lua.eval("""{Encode=function(_,v) return reviewEncode(v) end,
            Decode=function(_,v) return reviewDecode(v) end}""")
        return self.deps.RedundantStore.new(files,codec,self.deps.sha256,'IdleMafiaEmber/checkpoints')
    def test_startup_restore_and_late_callbacks_never_read_or_enable(self):
        self.ember.Flush(); self.assertEqual(self.reads,[]); self.assertEqual(self.listings,[])
        self.button.options.Callback(None,None,self.f.table({'restored':True}))
        self.assertEqual(self.reads,[])
        self.app.Destroy(self.app); self.button.options.Callback(); self.ember.Flush()
        self.assertEqual(self.reads,[]); self.assertEqual(self.writes,[])
    def test_hundred_terminal_rows_still_unknown_and_original_bytes_preserved(self):
        rows=[dict(id=i,feature='jobs',remote='PRIVATE REMOTE',identity='PRIVATE IDENTITY',
            state='confirmed',at=i,details='PRIVATE DETAILS') for i in range(1,101)]
        self.save('action-journal',dict(version=1,nextId=351932,entries=rows))
        before=dict(self.disk); report=self.click(); text=self.report_text()
        self.assertFalse(report.completeHistory); self.assertFalse(report.authorizesActivation)
        self.assertIn('100 retained',text); self.assertIn('351932',text)
        self.assertNotIn('PRIVATE',text); self.assertEqual(before,self.disk); self.assertEqual(self.writes,[])
        self.assertTrue(self.app.model.paused)
        self.assertFalse(any(v for k,v in self.app.model['values'].items() if k.endswith('.enabled')))
    def test_recognized_preferences_and_counts_are_metadata_only(self):
        self.save('settings',dict(version=17,jobMode='PRIVATE PREF',favorUsageCount=8))
        self.save('configs',dict(version=1,profiles={'PRIVATE NAME':dict(settings={'token':'PRIVATE'},enabled={})},autoload='PRIVATE NAME'))
        self.save('market-flip',dict(version=1,account='user-a',placeId=73897506680154,spent=25,tx={'secret':'PRIVATE'},utc=3))
        self.save('high-value-targets',dict(version=1,targets={'PRIVATE TARGET':{}},daily={'day':1,'counts':{}}))
        self.click(); text=self.report_text()
        for expected in ('v17','1 profiles','spent=25','1 targets'): self.assertIn(expected,text)
        self.assertNotIn('PRIVATE',text)
    def test_v17_unset_days_and_exact_counter_boundaries_are_recognized(self):
        self.save('settings',dict(version=17,favorUsageDay=-1,favorUsageCount=0,
            sabotageUsageDay=-1,sabotageUsageCount=0,sabotageAttemptDay=-1,sabotageAttemptCount=0))
        before=dict(self.disk);self.click();text=self.report_text()
        self.assertIn('Recognized v17',text);self.assertNotIn('Malformed preferences',text)
        for name in ('favorUsageDay','sabotageUsageDay','sabotageAttemptDay'):
            self.assertIn(name+'=-1 (unset)',text)
        self.assertEqual(self.disk,before);self.assertEqual(self.writes,[])
        self.save('settings',dict(version=17,favorUsageDay=1000000000000,favorUsageCount=1000000000,
            sabotageUsageDay=0,sabotageUsageCount=0,sabotageAttemptDay=1,sabotageAttemptCount=1))
        self.click();self.assertIn('Recognized v17',self.report_text())
        self.assertNotIn('Malformed preferences',self.report_text())

    def test_v17_saved_counter_invalid_values_are_not_coerced_or_normalized(self):
        for field,values in (
            ('favorUsageDay',[-2,-0.5,1.5,'-1','2026-11-03',1000000000001]),
            ('sabotageUsageDay',[-2,1000000000001]),
            ('sabotageAttemptDay',[-2,1000000000001]),
            ('favorUsageCount',[-1,0.5,'0',1000000001]),
            ('sabotageUsageCount',[-1,1000000001]),
            ('sabotageAttemptCount',[-1,1000000001])):
            for value in values:
                with self.subTest(field=field,value=value):
                    self.save('settings',{'version':17,field:value})
                    before=dict(self.disk);self.click()
                    self.assertIn('Malformed preferences or saved counters',self.report_text())
                    self.assertEqual(self.disk,before)
        self.assertEqual(self.writes,[])

    def test_malformed_partial_and_unsupported_not_empty(self):
        self.save('action-journal',dict(version=1,nextId=3,entries=[{'id':1}]))
        self.save('configs',dict(version=1,profiles={'bad':{}}))
        self.save('settings',dict(version=999,secret='PRIVATE'))
        self.click(); text=self.report_text()
        self.assertIn('Malformed',text); self.assertIn('Unsupported',text)
        self.assertNotIn('PRIVATE',text)
    def test_oversize_readerror_and_missing_listing_explicit_unknown(self):
        for kind in ('oversize','readerror'):
            with self.subTest(kind=kind):
                self.setUp()
                if kind=='oversize': self.disk[self.legacy+'settings.json']='x'*2097153
                if kind=='readerror':
                    self.disk[self.legacy+'settings.json']='{}';self.fail_path=self.legacy+'settings.json'
                if kind=='missing': self.env.listfiles=None
                self.click(); self.assertIn('Unknown',self.report_text())
                self.assertNotIn('PRIVATE ERROR',self.report_text());self.assertEqual(self.writes,[])
    def test_missing_listing_is_disabled_without_reads(self):
        self.env.listfiles=None
        self.app.Destroy(self.app)
        self.app,self.ember=self.f.app()
        self.assertIn('unavailable',self.app.ui.profiles.savedStateStatus.Get(self.app.ui.profiles.savedStateStatus))
        button=next(h for h in self.app.ui.window.handles.values()
            if h.kind=='Button' and h.options.Text=='Review saved state')
        self.assertTrue(button.options.Disabled)
        button.Click(button);self.ember.Flush()
        self.assertIsNone(self.app.savedStateReview);self.assertEqual(self.reads,[])
    def test_source_change_and_repeated_bounded_review(self):
        self.save('settings',dict(version=17))
        self.changed=self.legacy+'settings.json'
        self.click(); self.assertFalse(self.app.savedStateReview.rechecked)
        self.assertIn('changed',self.report_text())
        self.changed=None;self.reads.clear();self.click()
        self.assertTrue(self.app.savedStateReview.rechecked)
        self.assertLessEqual(len(self.reads),24)
        self.assertTrue(all(self.reads.count(path)<=2 for path in set(self.reads)))
    def test_checkpoint_scope_and_strict_digest_validation(self):
        store=self.store(); key='idle-mafia-ember:checkpoint:v1:6:user-a14:738975066801543:old'
        store.Write(store,key,self.f.table({'version':1,'account':'user-a','place':'73897506680154','release':'old','pending':{'secret':'PRIVATE'}}))
        self.click();text=self.report_text();self.assertIn('other release',text);self.assertNotIn('PRIVATE',text)
        a,b=store.Paths(store,key);self.disk[a]=self.disk[a].replace('"digest":"','"digest":"bad')
        self.click();self.assertIn('Unknown',self.report_text())
    def test_unrelated_account_is_not_shown(self):
        store=self.store(); key='idle-mafia-ember:checkpoint:v1:6:user-b14:738975066801543:old'
        store.Write(store,key,self.f.table({'version':1,'account':'user-b','place':'73897506680154','release':'old','pending':{'secret':'PRIVATE'}}))
        self.disk['IdleMafiaFluent/73897506680154/user-b/settings.json']='PRIVATE'
        self.reads.clear();self.click();text=self.report_text()
        self.assertNotIn('user-b',text);self.assertNotIn('PRIVATE',text)
        self.assertFalse(any('/user-b/' in path for path in self.reads))
    def test_close_during_read_cancels_before_next_io_and_discards_report(self):
        self.lua.globals().reviewApp=self.app
        self.close_on_read=True
        self.disk[self.legacy+'settings.json']='{}'
        self.click();self.assertFalse(self.app.alive);self.assertIsNone(self.app.savedStateReview)
        self.assertEqual(self.listings,[]);self.assertEqual(self.writes,[])


    def test_response_received_and_raw_sent_remain_review_needed(self):
        rows=[dict(id=i,feature='shop',remote='PRIVATE',identity='PRIVATE',state=state,at=1.5,
            finishedAt=2.5) for i,state in enumerate(['confirmed']*56+['response_received']*44,1)]
        self.save('action-journal',dict(version=1,nextId=351932,entries=rows))
        self.click();text=self.report_text()
        for value in ('confirmed=56','response_received=44','44 rows need review','not settled success'):
            self.assertIn(value,text)
        rows[0]['state']='sent';self.save('action-journal',dict(version=1,nextId=351932,entries=rows))
        self.click();text=self.report_text();self.assertIn('sent=1',text);self.assertIn('45 rows need review',text)
        self.assertNotIn('interrupted=1',text)

    def test_real_crew_producer_and_side_fact_are_read_only_scoped(self):
        import test_crew_replacement as crew_fixture
        producer=crew_fixture.CrewReplacementTests();producer.setUp()
        proposal,before=producer.prepare()
        producer.tx.MarkSending(producer.tx,before,1);producer.tx.Close(producer.tx)
        self.assertTrue(producer.tx.RecordAbandonedUnsent(producer.tx,proposal.actionKey))
        store=self.store()
        for key,value in producer.storage.data.items():
            self.assertTrue(store.Write(store,key,self.f.table(plain(value))))
        before=dict(self.disk);self.reads.clear();self.click();text=self.report_text()
        self.assertIn('Recognized crew-replacement',text);self.assertIn('other release',text)
        self.assertIn('attempted=1',text);self.assertIn('2 relevant',text)
        self.assertEqual(before,self.disk);self.assertEqual(self.writes,[])
        self.assertFalse(self.app.savedStateReview.authorizesActivation)
        self.assertTrue(all(self.reads.count(path)<=2 for path in set(self.reads)))

    def test_real_crew_other_account_is_withheld(self):
        import test_crew_replacement as crew_fixture
        producer=crew_fixture.CrewReplacementTests();producer.setUp()
        producer.h.session['account']='user-b';producer.load_components();producer.prepare()
        store=self.store()
        for key,value in producer.storage.data.items(): store.Write(store,key,self.f.table(plain(value)))
        self.click();text=self.report_text()
        self.assertIn('1 other-account/place records withheld',text)
        self.assertNotIn('user-b',text);self.assertNotIn('attempted=1',text)

    def test_digest_mismatch_shows_partial_slots_without_recovering_old(self):
        store=self.store();key='idle-mafia-ember:checkpoint:v1:6:user-a14:738975066801543:old'
        for value in (1,2): store.Write(store,key,self.f.table({'version':1,'records':[],'requestHighwater':value}))
        a,b=store.Paths(store,key);self.disk[b]='damaged PRIVATE TOKEN'
        before=dict(self.disk);self.click();text=self.report_text()
        self.assertFalse(self.app.savedStateReview.rechecked)
        self.assertIn('Observed checkpoint slot',text);self.assertIn('unrecoverable strict slot',text)
        self.assertNotIn('requestHighwater=1',text);self.assertNotIn('PRIVATE',text)
        self.assertEqual(before,self.disk)

    def test_aggregate_budget_and_listing_limits(self):
        for name in ('settings','configs','action-journal'):
            self.disk[self.legacy+name+'.json']=' '*1500000+'{}'
        self.click();text=self.report_text()
        self.assertFalse(self.app.savedStateReview.rechecked);self.assertIn('size limit',text)
        self.assertLessEqual(len(self.reads),3)
        self.setUp();self.list_override=['IdleMafiaEmber/checkpoints/'+str(i) for i in range(513)]
        self.click();self.assertFalse(self.app.savedStateReview.rechecked)
        self.assertIn('strict discovery failed',self.report_text())
        self.assertLessEqual(len(self.reads),24)

    def test_listing_path_sparse_duplicate_and_change_are_unknown(self):
        for listing in (['wrong/path'],['IdleMafiaEmber/checkpoints/a']*2,{2:'IdleMafiaEmber/checkpoints/a'}):
            with self.subTest(listing=listing):
                self.setUp();self.list_override=listing;self.click()
                self.assertFalse(self.app.savedStateReview.rechecked)
                self.assertIn('strict discovery failed',self.report_text())
        self.setUp()
        def changed_listing(path):
            self.listings.append(path)
            return self.f.table([] if len(self.listings)==1 else [path+'/new-file'])
        self.lua.globals().reviewList=changed_listing
        self.click();self.assertFalse(self.app.savedStateReview.rechecked)
        self.assertIn('source changed',self.report_text())

    def test_paging_all_records_requires_no_additional_reads(self):
        self.click();before=list(self.reads);pages={}
        buttons={h.options.Text:h for h in self.app.ui.window.handles.values() if h.kind=='Button'}
        for expected in (1,2,3):
            pages[expected]=[h.Get(h) for h in self.app.ui.profiles.savedStateRows.values()]
            self.assertIn('Page '+str(expected),self.app.ui.profiles.savedStatePage.Get(self.app.ui.profiles.savedStatePage))
            buttons['Next review page'].Click(buttons['Next review page']);self.ember.Flush()
        self.assertTrue(any('settings:' in value for value in pages[1]))
        self.assertTrue(any('Ember discovery:' in value for value in pages[3]))
        self.assertEqual(self.reads,before)
        buttons['Previous review page'].Click(buttons['Previous review page']);self.ember.Flush()
        self.assertEqual(self.reads,before)

    def test_unknown_family_and_scope_never_echo_private_key_content(self):
        store=self.store()
        store.Write(store,'idle-mafia-ember:PRIVATE-TOKEN:v1:6:user-a14:738975066801543:old',self.f.table({'secret':'PRIVATE'}))
        self.click();text=self.report_text();self.assertIn('Unknown checkpoint family',text)
        self.assertNotIn('PRIVATE',text)

    def test_reentrant_review_is_rejected_and_all_callbacks_remain_opt_in(self):
        self.save('settings',{'version':17});self.reenter=True
        self.click();self.assertTrue(self.app.savedStateReview.rechecked)
        self.assertFalse(self.app.reviewBusy);self.assertEqual(self.reads.count(self.legacy+'settings.json'),2)
        self.assertIsNone(self.app.profileStore)
        before=list(self.reads)
        for origin in ({'initial':True},{'restored':True},{'reapplied':True}):
            self.button.options.Callback(None,None,self.f.table(origin))
        self.assertEqual(self.reads,before)

    def test_full_512_slot_inventory_remains_bounded_and_every_row_pageable(self):
        store=self.store()
        for i in range(512):
            key='idle-mafia-ember:checkpoint:v1:6:user-a14:738975066801543:old:'+str(i)
            store.Write(store,key,self.f.table({'version':1,'records':[]}))
        self.reads.clear();before=dict(self.disk);self.click()
        self.assertTrue(self.app.savedStateReview.rechecked)
        self.assertEqual(len(self.app.savedStateReview.rows),525)
        self.assertLessEqual(len(self.reads),1048)
        self.assertTrue(all(self.reads.count(path)<=2 for path in set(self.reads)))
        self.assertEqual(self.disk,before);self.assertEqual(self.writes,[])

    def test_genuine_test_entry_read_capabilities_survive_memory_cache_fallback(self):
        source=(ROOT/'TestEntry.luau').read_text(encoding='utf-8')
        fragment=source[source.index('local files, folders'):source.index('local app, reason')]
        self.lua.globals().hashApi=self.lua.table()
        for key in ('isfile','readfile','listfiles'): self.lua.globals()[key]=self.env[key]
        result=self.lua.execute(fragment+'\nreturn env')
        self.assertEqual(lua_type(result.savedStateReadApi.listfiles),'function')
        self.assertEqual(lua_type(result.savedStateReadApi.readfile),'function')
        self.assertFalse(result.isfile('a'))
        self.assertEqual(self.reads,[]);self.assertEqual(self.writes,[])
        self.lua.globals().listfiles=None
        result=self.lua.execute(fragment+'\nreturn env')
        self.assertIsNone(result.savedStateReadApi.listfiles)

    def test_inert_bootstrap_forwards_real_review_dependencies_without_owners_or_native_requires(self):
        self.app.Destroy(self.app)
        g=self.lua.globals();g.bootDeps=self.fixture_deps;g.bootHttp=self.http
        g.bootModule=self.lua.execute((ROOT/'src/App.luau').read_text(encoding='utf-8'))
        g.bootEnv=self.env;g.bootEmber=self.ember
        adapters=self.lua.execute("""
            return {Loader={start=function(_,_,_,_,d)
                for k,v in pairs(bootDeps) do if d[k]==nil then d[k]=v end end
                return bootModule.start(d),nil end},Manifest={},fetch=function() end,cache={},
                compile=function() end,clientRequire=function() error('native require forbidden') end,
                clientHash=function(v) return reviewHash(v) end,executorEnv=bootEnv,
                Ember=bootEmber,executionRegistry={sentinel=true},legacyRegistry={IdleMafiaFluentHub={alive=true}},
                clientGame={PlaceId=73897506680154,GetService=function(_,name)
                    if name=='Players' then return {LocalPlayer={Name='user-a'}} end
                    return bootHttp end}}
        """)
        release=self.f.table({'commit':'a'*40,'fingerprint':'b'*64,'place':'73897506680154',
            'gameVersion':'fixture','directory':'IdleMafiaEmber','manifest':{'releaseCommit':'a'*40}})
        bootstrap=self.lua.execute((ROOT/'Bootstrap.luau').read_text(encoding='utf-8'))
        self.app,reason=bootstrap.start(release,adapters,False)
        self.assertIsNone(reason);self.assertEqual(self.reads,[]);self.assertEqual(self.listings,[])
        self.assertTrue(adapters.legacyRegistry.IdleMafiaFluentHub.alive)
        self.assertEqual(list(adapters.executionRegistry.keys()),['sentinel'])
        self.button=next(h for h in self.app.ui.window.handles.values()
            if h.kind=='Button' and h.options.Text=='Review saved state')
        self.save('settings',{'version':17});self.click()
        self.assertIn('v17',self.report_text());self.assertEqual(self.writes,[])

if __name__=='__main__': unittest.main()
