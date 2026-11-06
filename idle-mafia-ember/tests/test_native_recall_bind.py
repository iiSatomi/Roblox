"""Full native source hash, captured closures, actual worker exclusion and epochs."""
import unittest
from engine_harness import lua_table
from recall_source_fixture import make_recall_client

class NativeRecallBindTests(unittest.TestCase):
    def setUp(self):
        self.h,self.f=make_recall_client();self.module=self.h.load('src/tabs/territory/NativeRecallLease.luau')
    def bind(self):
        self.assertIsNotNone(self.module.bind,'Full native Recall binding is missing')
        return self.module.bind(lua_table(self.h.lua,{'game':self.f.game,'env':self.f.env,'registry':self.f.registry,
            'requireModule':self.f.requireModule,'clock':self.h.clock,'account':'user-a'}))
    def proposal(self,owner):
        quote,why=owner.Quote(owner,0);self.assertIsNotNone(quote,why)
        p=self.h.proposal('station','recall:source');p.resources=self.h.lua.table();p.intent=self.h.lua.table(kind='territoryRecall',memberKey='id:guard')
        for key,value in self.f.target.items():p.intent[key]=value
        for key,value in quote.items():p.intent[key]=value
        return p
    def test_verified_builds_require_matching_source_and_unknown_build_is_refused(self):
        for version in (648, 653, 654, 655):
            with self.subTest(version=version):
                self.setUp(); self.f.game.PlaceVersion=version
                owner, why = self.bind(); self.assertIsNotNone(owner, why)
                self.assertIsNotNone(owner.Identity(owner)); owner.Close(owner)
        self.setUp(); self.f.game.PlaceVersion=656
        self.assertEqual(self.bind(), (None, 'Unreviewed Recall build'))

    def test_captured_native_source_parks_shared_cell_without_running_start_or_finish(self):
        owner,why=self.bind();self.assertIsNotNone(owner,why);p=self.proposal(owner)
        self.assertEqual((owner.Identity(owner).account,owner.Identity(owner).userId),('user-a',42))
        before=len(self.f.jobs);self.assertTrue(owner.Acquire(owner,p,45)[0]);self.assertTrue(self.f.api.busy())
        self.assertTrue(self.f.api.isPending('d1',42,2));self.f.api.start(lua_table(self.h.lua,[self.f.target]))
        self.assertEqual(len(self.f.jobs),before);self.assertEqual(self.f.calls,0)
        self.f.update(lua_table(self.h.lua,{'kind':'recall','requestId':p.intent.requestId,'result':{'ok':True,'settled':[self.f.target]}}))
        self.assertTrue(owner.Owns(owner,p));owner.Release(owner,p);self.assertFalse(self.f.api.busy())
    def test_wrong_full_source_and_context_identity_refuse_binding(self):
        self.f.badSource=True;self.assertIsNone(self.bind()[0])
        self.setUp();self.f.ctx.player=self.h.lua.table(UserId=42,Name='user-a');self.assertIsNone(self.bind()[0])
    def test_unknown_prior_native_start_is_not_adopted_even_when_pending_clears(self):
        self.f.api.start(lua_table(self.h.lua,[self.f.target]))
        self.f.update(lua_table(self.h.lua,{'kind':'recall','requestId':1000000,'result':{'ok':True,'settled':[self.f.target]}}))
        self.assertFalse(self.f.api.busy());owner,why=self.bind();self.assertIsNotNone(owner,why)
        self.assertIsNone(owner.Quote(owner,0)[0]);self.assertEqual(self.f.calls,0)
    def test_same_loaded_epoch_survives_new_owner_but_native_counter_change_retires_it(self):
        owner,why=self.bind();self.assertIsNotNone(owner,why);p=self.proposal(owner)
        owner.Acquire(owner,p,45);owner.Release(owner,p)
        newer,why=self.bind();self.assertIsNotNone(newer,why)
        self.assertEqual(newer.Identity(newer).nativeEpoch,owner.Identity(owner).nativeEpoch)
        self.assertEqual(newer.Quote(newer,0)[0].requestId,1000001)
        self.f.api.start(lua_table(self.h.lua,[self.f.target]));self.assertIsNone(newer.Quote(newer,0)[0])
    def test_native_confirmation_and_presence_blocks_are_never_closed_or_solved(self):
        owner,why=self.bind();self.assertIsNotNone(owner,why)
        self.f.confirm.Visible=True;self.assertIsNone(owner.Quote(owner,0)[0]);self.assertTrue(self.f.confirm.Visible)
        self.f.confirm.Visible=False;self.f.presence=True;self.assertIsNone(owner.Quote(owner,0)[0]);self.assertTrue(self.f.presence)
    def test_original_token_can_be_cleaned_after_build_changes_without_clearing_foreign_state(self):
        owner,why=self.bind();self.assertIsNotNone(owner,why);p=self.proposal(owner);owner.Acquire(owner,p,45)
        self.f.game.PlaceVersion=654;self.assertFalse(owner.Owns(owner,p));self.assertTrue(owner.Release(owner,p)[0]);self.assertFalse(self.f.api.busy())

    def test_native_current_member_and_numeric_user_properties_are_rechecked(self):
        owner,why=self.bind();self.assertIsNotNone(owner,why);p=self.proposal(owner)
        self.assertIsNotNone(owner.CheckTarget,'Native deployment guard is missing')
        self.f.ctx.State.data=lua_table(self.h.lua,{'userId':42,'family':{'id':'own-family'},'crew':[{'name':'Player'},
            {'name':'Guard','rarity':4,'healId':'guard','duty':'d1','dutyToken':'deployment-a','dutyAt':900}]})
        p.intent.familyId='own-family';self.assertTrue(owner.CheckTarget(owner,p))
        self.f.ctx.State.data.crew[2].healId='replacement';self.assertFalse(owner.CheckTarget(owner,p))
        self.f.ctx.State.data.crew[2].healId='guard';self.f.player.UserId=43
        self.assertFalse(owner.CheckTarget(owner,p));self.assertIsNone(owner.Identity(owner))

    def test_server_job_change_retires_source_and_keeps_exact_token_cleanup(self):
        owner,why=self.bind();self.assertIsNotNone(owner,why);p=self.proposal(owner);self.assertTrue(owner.Acquire(owner,p,45)[0])
        self.f.game.JobId='new-job'
        self.assertIsNone(owner.Identity(owner));self.assertFalse(owner.Owns(owner,p))
        self.assertTrue(owner.Release(owner,p)[0]);self.assertFalse(self.f.api.busy())
        self.f.game.JobId='recall-job';self.assertIsNone(owner.Quote(owner,0)[0])

    def test_static_context_replacement_retires_identity_even_if_context_is_restored(self):
        owner,why=self.bind();self.assertIsNotNone(owner,why)
        self.f.env.setupvalue(self.f.api.start,6,self.h.lua.table())
        self.assertIsNone(owner.Identity(owner))
        self.f.env.setupvalue(self.f.api.start,6,self.f.ctx)
        self.assertIsNone(owner.Identity(owner));self.assertIsNone(owner.Quote(owner,0)[0])
