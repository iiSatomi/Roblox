"""Owned native heal timer evidence survives passive Stamina and uncertain replies."""
import json
import unittest
from contextlib import contextmanager

import test_crew_heal_runtime as fixture
from engine_harness import lua_table


class CrewHealOwnedSettlementTests(unittest.TestCase):
    @contextmanager
    def fixture(self,reply=None,injury=1601):
        f=fixture.CrewHealRuntimeTests();f.setUp()
        try:
            if reply is not None:f.f.executor.reply=lua_table(f.h.lua,reply)
            f.choose();f.step(injury=injury);f.f.drain()
            self.assertEqual(len(f.f.executor.calls),1)
            self.action=f.f.runtime.checkpoint.Records(f.f.runtime.checkpoint)[1].actionKey
            yield f
        finally:f.tearDown()

    def observe(self,f,raw,at=None):
        f.h.at(raw.capturedAt if at is None else at);f.f.app.Step(f.f.app,raw)

    def held(self,f):
        records=f.f.runtime.checkpoint.Records(f.f.runtime.checkpoint)
        self.assertEqual(len(records),1)
        self.assertEqual(records[1].actionKey,self.action)
        self.assertEqual(records[1].resources.stamina,5)
        self.assertEqual(records[1].custody.funds.stamina,5)
        self.assertEqual(len(f.f.executor.calls),1)

    def restart(self,f):
        def wire(value):
            if not hasattr(value,'items'):return value
            entries=dict(value.items())
            if entries and set(entries)==set(range(1,len(entries)+1)):
                return [wire(entries[i]) for i in range(1,len(entries)+1)]
            return {k:wire(v) for k,v in entries.items()}
        for key,value in list(f.f.storage.data.items()):
            f.f.storage.data[key]=lua_table(f.h.lua,json.loads(json.dumps(wire(value))))
        f.f.restart()

    def test_pending_and_busy_both_outcomes_keep_original_heal_custody_across_restart(self):
        for code in ('pending','busy'):
            for ok in (False,True):
                with self.subTest(code=code,ok=ok),self.fixture({'ok':ok,'code':code}) as f:
                    injury,stamina=(1301,10) if ok else (1601,15)
                    f.step(2,stamina,injury);self.held(f)
                    self.observe(f,f.raw(46,stamina,injury),46);f.f.drain();self.held(f)
                    self.restart(f)
                    after=f.raw(0,stamina,injury);after.native.serverNow=1005
                    self.observe(f,after);f.choose();self.observe(f,after);f.f.drain();self.held(f)

    def test_exact_owned_partial_heal_settles_with_passive_stamina_without_inventing_regen(self):
        for stamina in (11,15,16.25):
            with self.subTest(stamina=stamina),self.fixture() as f:
                f.f.app.Set(f.f.app,'crewHeal.enabled',False)
                f.step(2,stamina,1301)
                self.assertEqual(f.f.runtime.Status(f.f.runtime).outcomes.crewHeal,'confirmed')
                self.assertEqual(len(f.f.runtime.checkpoint.Records(f.f.runtime.checkpoint)),0)
                self.assertEqual(len(f.f.executor.calls),1)

    def test_original_baseline_recovers_after_json_restart_with_passive_stamina(self):
        with self.fixture() as f:
            records=f.f.runtime.checkpoint.Records(f.f.runtime.checkpoint)
            data=f.f.runtime.checkpoint.Recovery(f.f.runtime.checkpoint,records[1].actionKey)[0]
            original=set(data.baseline.keys())
            self.restart(f)
            after=f.raw(0,11,1301);after.native.serverNow=1005;self.observe(f,after)
            self.assertEqual(f.f.runtime.Status(f.f.runtime).recoveries.crewHeal,'confirmed')
            self.assertEqual(len(f.f.runtime.checkpoint.Records(f.f.runtime.checkpoint)),0)
            self.assertEqual(set(data.baseline.keys()),original)
            self.assertEqual(len(f.f.executor.calls),1)

    def test_passive_path_refuses_wrong_episode_identity_clock_custody_or_debit(self):
        for case in ('sameclock','missingclock','wrongtimer','noeffect','lessstamina','wrongmember',
                     'duplicate','duty','training','rolling','rolling_string','rolling_table','rolling_number',
                     'partial','negative','nonfinite'):
            with self.subTest(case=case),self.fixture({'ok':case!='negative'}) as f:
                after=f.raw(2,11,1301)
                if case=='sameclock':after.native.serverNow=1001
                elif case=='missingclock':after.native.serverNow=None
                elif case=='wrongtimer':after.native.crew[2].injuredUntil=1300
                elif case=='noeffect':after.native.crew[2].injuredUntil=1601
                elif case=='lessstamina':after.native.pools.stamina=9
                elif case=='wrongmember':after.native.crew[2].healId='other-member'
                elif case=='duplicate':after.native.crew[3].healId='injury-a'
                elif case=='duty':after.native.crew[2].duty=lua_table(f.h.lua,{'districtId':'d'})
                elif case=='training':after.native.crew[2].training=lua_table(f.h.lua,{'ends':2000})
                elif case=='rolling':after.native.crew[2].rolling=True
                elif case=='rolling_string':after.native.crew[2].rolling='unverified'
                elif case=='rolling_table':after.native.crew[2].rolling=f.h.lua.table()
                elif case=='rolling_number':after.native.crew[2].rolling=0
                elif case=='partial':after.native.fullSync=False
                elif case=='nonfinite':after.native.pools.stamina=float('inf')
                self.observe(f,after);self.held(f)

    def test_finished_timer_before_original_expiry_can_settle_but_natural_expiry_cannot(self):
        for now,expected in ((1002,'confirmed'),(1200,None)):
            with self.subTest(now=now),self.fixture(injury=1100) as f:
                after=f.raw(2,14,0);after.native.serverNow=now;self.observe(f,after)
                self.assertEqual(f.f.runtime.Status(f.f.runtime).outcomes.crewHeal,expected)
                self.assertEqual(len(f.f.executor.calls),1)
