"""Owned ordinary Lookup keeps exact identity, source ownership and native pacing."""
import unittest

from engine_harness import Harness, lua_table


class CombatSavedLookupTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.source = self.h.lua.execute("""return {searchActive=true,
            Current=function(self,remote) return remote~='SearchTarget' or self.searchActive end}""")
        self.query = self.h.load('src/tabs/combat/HitListQuery.luau').new(
            lua_table(self.h.lua,self.h.session),'a'*64,self.source)
        self.target = lua_table(self.h.lua,{'userId':456,'name':'Saved'})
        self.other = lua_table(self.h.lua,{'userId':789,'name':'Other'})

    def raw(self, captured=0, server=None):
        return self.h.snapshot(revision=captured+1,captured_at=captured,
            native={'fullSync':True,'serverNow':100+captured if server is None else server,
                'family':{'id':'own'},'level':10})

    def refresh(self, raw):
        q = self.query
        request,reason = q.Prepare(q,raw)
        self.assertIsNone(reason)
        staged,reason = q.Accept(q,raw,request,lua_table(self.h.lua,{'ok':True,'list':[]}))
        self.assertIsNone(reason)
        self.assertTrue(q.Commit(q,staged))

    def search(self, raw, target=None, found=True):
        q = self.query
        target = self.target if target is None else target
        self.refresh(raw)
        request,reason = q.PrepareSavedSearch(q,raw,target)
        self.assertIsNone(reason)
        rows = [{'userId':999,'name':'Unrelated','level':10,'stamina':1,'shielded':False}]
        if found: rows.append({'userId':target.userId,'name':target.name,'level':10,'stamina':1,'shielded':False})
        staged,reason = q.AcceptSavedSearch(q,raw,request,lua_table(self.h.lua,{
            'ok':True,'search':target.name,'list':rows}))
        self.assertIsNone(reason)
        self.assertTrue(q.CommitSavedSearch(q,staged))
        return request

    def test_lookup_projects_only_exact_owned_seed_and_expires_after_ten_seconds(self):
        raw = self.raw()
        call = self.search(raw)
        self.assertEqual((call.remote,call.arity,call.args[1]),('SearchTarget',1,'Saved'))
        rows = self.query.Read(self.query,raw).rows
        self.assertEqual([row.userId for row in rows.values()],[456])
        now = self.raw(11)
        self.refresh(now)
        self.assertEqual(len(self.query.Read(self.query,now).rows),0)

    def test_global_sixty_second_and_target_thirty_minute_pacing_require_both_clocks(self):
        self.search(self.raw(),found=False)
        for captured,server in ((59,160),(60,159)):
            with self.subTest(captured=captured,server=server):
                self.assertFalse(self.query.SearchReady(self.query,self.raw(captured,server),self.other))
        self.assertTrue(self.query.SearchReady(self.query,self.raw(60),self.other))
        self.assertFalse(self.query.SearchReady(self.query,self.raw(60),self.target))
        for captured,server in ((1799,1900),(1800,1899)):
            self.assertFalse(self.query.SearchReady(self.query,self.raw(captured,server),self.target))
        self.assertTrue(self.query.SearchReady(self.query,self.raw(1800),self.target))
        # Failed/no-match owned reads still consume spacing; refreshing metadata
        # cannot manufacture another attempt within the same target window.
        self.refresh(self.raw(1799))
        self.assertIsNone(self.query.PrepareSavedSearch(self.query,self.raw(1799),self.target)[0])

    def test_source_retirement_discards_lookup_and_never_rearms_when_callback_recovers(self):
        raw = self.raw()
        self.search(raw)
        self.source.searchActive = False
        self.assertEqual(len(self.query.Read(self.query,raw).rows),0)
        self.source.searchActive = True
        self.assertFalse(self.query.SearchReady(self.query,self.raw(1800),self.target))
        self.assertIsNone(self.query.PickSavedSearch(self.query,self.raw(1800),
            lua_table(self.h.lua,[self.target,self.other]),32))

    def test_changed_quote_scope_or_refreshed_generation_cannot_admit_late_search_reply(self):
        for changed in ('level','generation'):
            with self.subTest(changed=changed):
                self.setUp()
                raw = self.raw()
                self.refresh(raw)
                request,reason = self.query.PrepareSavedSearch(self.query,raw,self.target)
                self.assertIsNone(reason)
                if changed == 'level': raw.native.level = 11
                else: self.refresh(raw)
                staged,reason = self.query.AcceptSavedSearch(self.query,raw,request,lua_table(self.h.lua,{
                    'ok':True,'search':'Saved','list':[{'userId':456,'name':'Saved','level':10}]}))
                self.assertIsNone(staged)
                self.assertIsNotNone(reason)


if __name__ == '__main__': unittest.main()
