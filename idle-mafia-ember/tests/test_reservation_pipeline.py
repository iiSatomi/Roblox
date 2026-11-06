"""Shared broker admission and write-ahead custody, using offline transports."""
import unittest

from engine_harness import Harness, lua_table


class ReservationPipelineTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.module = self.h.load("src/engine/ResourceReservations.luau")
        self.cp_module = self.h.load("src/storage/Checkpoint.luau")
        self.storage = self.h.lua.execute("""return {strictRecovery=true,data={},
            Read=function(self,key) return self.data[key] end,
            Write=function(self,key,value) self.data[key]=value return true end}""")
        self.checkpoint = self.cp_module.new(self.storage, None, self.module)
        self.checkpoint.Load(self.checkpoint, "user-a", self.h.session["place"], "release-a")
        self.h.lua.globals().checkpoint = self.checkpoint
        self.h.lua.globals().hold = None
        self.manager = self.module.new(lua_table(self.h.lua, self.h.session),
            self.h.lua.eval("function() return checkpoint:Records() end"),
            self.h.lua.execute("return {{id='store',read=function() return hold end}}"))
        self.h.policy.reservations = self.manager
        self.session = self.h.load("src/engine/Session.luau").new(
            self.h.broker, self.checkpoint, lua_table(self.h.lua, self.h.session))

    def tearDown(self):
        self.session.Close(self.session)

    def raw(self):
        return self.h.snapshot(native={"fullSync": True, "cash": 1000,
            "inventory": {"w_a": 3}, "inventoryBound": {}, "crew": [
                {"name": "YOU"}, {"name": "A", "healId": "h1"}]})

    def proposal(self, feature="collectionDonate", amount=2):
        proposal = self.h.proposal(feature, feature + ":test")
        proposal.intent = lua_table(self.h.lua, {"kind": "collectionDonate", "itemId": "w_a", "amount": amount})
        proposal.resources = lua_table(self.h.lua, {"w_a": amount})
        return proposal

    def hold(self, amount=2):
        self.h.lua.globals().hold = lua_table(self.h.lua, {
            "account": "user-a", "place": self.h.session["place"], "release": "release-a",
            "feature": "marketSell", "claims": {"members": {}, "items": {"L:w_a": amount},
                "funds": {}, "allCrew": False}})

    def test_ordinary_offer_blocks_held_items_and_allows_one_spare_copy(self):
        self.hold()
        self.assertEqual(self.session.Offer(self.session, self.proposal(), self.raw())[0], "blocked")
        self.assertEqual(len(self.h.transport.sent), 0)
        self.assertEqual(self.session.Offer(self.session, self.proposal(amount=1), self.raw())[0], "admitted")
        self.assertEqual(self.session.Tick(self.session, self.raw()), "sent")
        self.assertEqual(self.checkpoint.Records(self.checkpoint)[1].custody["items"]["L:w_a"], 1)

    def test_reservation_changed_after_admission_blocks_before_checkpoint_or_send(self):
        self.assertEqual(self.session.Offer(self.session, self.proposal(), self.raw())[0], "admitted")
        self.hold()
        self.assertEqual(self.session.Tick(self.session, self.raw()), "reservation_blocked")
        self.assertEqual(len(self.h.transport.sent), 0)
        self.assertEqual(len(self.checkpoint.Records(self.checkpoint)), 0)

    def test_timeout_keeps_exact_custody_across_reload_and_rejects_module_downgrade(self):
        proposal = self.proposal()
        # Untrusted caller custody must be discarded during contract validation.
        proposal.custody = lua_table(self.h.lua, {"allCrew": True})
        self.assertEqual(self.session.Offer(self.session, proposal, self.raw())[0], "admitted")
        self.assertEqual(self.session.Tick(self.session, self.raw()), "sent")
        self.h.at(45)
        self.assertEqual(self.session.Tick(self.session, self.raw()), "skipped_unconfirmed")
        restarted = self.cp_module.new(self.storage, None, self.module)
        records, reason = restarted.Load(restarted, "user-a", self.h.session["place"], "release-a")
        self.assertIsNone(reason)
        self.assertEqual(records[1].custody["items"]["L:w_a"], 2)
        records[1].custody["items"]["L:w_a"] = 999
        self.assertEqual(restarted.Records(restarted)[1].custody["items"]["L:w_a"], 2)
        downgraded = self.cp_module.new(self.storage)
        self.assertIsNone(downgraded.Load(downgraded, "user-a", self.h.session["place"], "release-a")[0])

    def test_old_item_request_does_not_block_disjoint_origin_or_spare_funding(self):
        old = self.proposal("chests", 1)
        old.custody = lua_table(self.h.lua, {"members": {}, "items": {"B:w_a": 1},
            "funds": {}, "allCrew": False})
        self.assertTrue(self.checkpoint.Save(self.checkpoint, old)[0])
        self.assertEqual(self.session.Offer(self.session, self.proposal(), self.raw())[0], "admitted")

    def test_queued_dispatch_rechecks_new_store_hold_and_clears_only_unsent_record(self):
        self.h.lua.globals().runQueued = None
        self.h.transport.Send = self.h.lua.eval("""function(self,p,cb,canDispatch,token,unsent)
            runQueued=function()
                if not canDispatch() then unsent() return end
                self.sent[#self.sent+1]=p
            end
            return true
        end""")
        self.session.Offer(self.session, self.proposal(), self.raw())
        self.assertEqual(self.session.Tick(self.session, self.raw()), "sent")
        self.hold()
        self.h.lua.globals().runQueued()
        self.assertEqual(len(self.h.transport.sent), 0)
        self.assertEqual(len(self.checkpoint.Records(self.checkpoint)), 0)
        self.assertIsNone(self.h.broker.active)
