"""Composite Market owners must not promote transient callbacks to terminal custody."""
import json
import unittest
from contextlib import contextmanager

import test_market_sell_runtime as sell_fixture
import test_market_flip_runtime as flip_fixture
from engine_harness import lua_table


class MarketCallbackCustodyTests(unittest.TestCase):
    @contextmanager
    def fixture(self,kind,ok,code):
        f=(sell_fixture.MarketSellRuntimeTests() if kind in ('list','withdraw')
           else flip_fixture.MarketFlipRuntimeTests())
        f.setUp()
        try:
            f.choose()
            if kind=='withdraw':
                for key,value in {'fromCollection':True,'maxWithdraw':1,'maxWithdrawAttempts':1}.items():
                    f.app.Set(f.app,'marketSell.custom.'+key,value)
                before=f.raw(loose=1,collected=2)
            else:before=f.raw()
            f.warm(before);f.app.Step(f.app,before)
            if kind=='flipList':
                f.executor.Drain(f.executor)
                before=f.raw(2,gold=12,loose=2);f.h.at(2);f.app.Step(f.app,before)
                f.warm(before);f.app.Step(f.app,before)
            reply={'ok':ok,'code':code}
            if kind=='withdraw':reply['moved']=1
            f.executor.reply=lua_table(f.h.lua,reply);f.executor.Drain(f.executor)
            expected=2 if kind=='flipList' else 1
            self.assertEqual(len(f.executor.calls),expected)
            records=f.runtime.checkpoint.Records(f.runtime.checkpoint)
            self.assertEqual(len(records),1)
            self.action=records[1].actionKey
            self.resources=dict(records[1].resources.items())
            self.calls=expected
            yield f
        finally:f.tearDown()

    def after(self,f,kind,ok,revision):
        if kind=='list':return f.raw(revision,loose=1 if ok else 2,listed=ok)
        if kind=='withdraw':return f.raw(revision,loose=2 if ok else 1,collected=1 if ok else 2)
        if kind=='buy':return f.raw(revision,gold=12 if ok else 20,loose=2 if ok else 1)
        raw=f.raw(revision,gold=12,loose=1 if ok else 2)
        if ok:
            raw.native.market.listings=lua_table(f.h.lua,{'listed':{'state':'live','item':'w_baton','indexed':1,
                'price':14,'qty':1,'left':1,'createdAt':1002,'itemOrigin':{'total':1,'free':0}}})
        return raw

    def observe(self,f,raw,at=None):
        f.h.at(raw.capturedAt if at is None else at);f.app.Step(f.app,raw)

    def held(self,f,code):
        records=f.runtime.checkpoint.Records(f.runtime.checkpoint)
        self.assertEqual(len(records),1)
        self.assertEqual(records[1].actionKey,self.action)
        self.assertEqual(dict(records[1].resources.items()),self.resources)
        data=f.runtime.checkpoint.Recovery(f.runtime.checkpoint,self.action)[0]
        self.assertEqual(data.reply.code,code)
        active=f.tab.transactions.Active(f.tab.transactions)
        self.assertIsNotNone(active)
        self.assertEqual(active.stage,'sent')
        self.assertEqual(active.reply.code,code)
        self.assertEqual(len(f.executor.calls),self.calls)

    def json_roundtrip(self,f):
        def wire(value):
            if not hasattr(value,'items'):return value
            entries=dict(value.items())
            if entries and set(entries)==set(range(1,len(entries)+1)):
                return [wire(entries[i]) for i in range(1,len(entries)+1)]
            return {k:wire(v) for k,v in entries.items()}
        for key,value in list(f.storage.data.items()):
            f.storage.data[key]=lua_table(f.h.lua,json.loads(json.dumps(wire(value))))

    def test_transient_codes_hold_both_outcomes_in_every_actual_market_stage(self):
        for kind in ('list','buy','withdraw','flipList'):
            for code in ('pending','busy','presence','rate_limited'):
                for ok in (True,False):
                    with self.subTest(kind=kind,code=code,ok=ok),self.fixture(kind,ok,code) as f:
                        self.observe(f,self.after(f,kind,ok,3));self.held(f,code)

    def test_pending_and_busy_custody_survives_timeout_json_restart_without_replay(self):
        for kind in ('list','buy','withdraw','flipList'):
            for ok in (True,False):
                code='pending' if ok else 'busy'
                with self.subTest(kind=kind,ok=ok),self.fixture(kind,ok,code) as f:
                    self.observe(f,self.after(f,kind,ok,46),46);f.executor.Drain(f.executor);self.held(f,code)
                    self.json_roundtrip(f);f.restart()
                    raw=self.after(f,kind,ok,0);raw.native.serverNow=1050
                    self.observe(f,raw);f.choose();self.observe(f,raw);f.executor.Drain(f.executor)
                    self.held(f,code)
