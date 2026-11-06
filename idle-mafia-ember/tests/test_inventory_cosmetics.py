"""Safe cosmetic changes use owned unbound copies and newer worn state."""
import unittest

from engine_harness import Harness, lua_table


class InventoryCosmeticTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        module = self.h.load("src/tabs/inventory/Cosmetics.luau")
        self.feature = module.new(lua_table(self.h.lua,
            {"ITEMS_BY_ID": {
                "bg_old": {"id": "bg_old", "kind": "background",
                           "atk": 1, "def": 1},
                "bg_new": {"id": "bg_new", "kind": "background",
                           "atk": 5, "def": 3}}}),
            "1" * 64, "release-a")
        self.before = self.h.snapshot(native={"fullSync": True,
            "equippedBackground": "bg_old", "inventory": {
                "bg_old": 1, "bg_new": 1}, "inventoryBound": {},
            "collectionBound": {}})
        self.context = lua_table(self.h.lua, {**self.h.session,
            "revision": 1, "capturedAt": 0,
            "cosmeticSourceKey": "1" * 64})

    def plan(self):
        view, reason = self.feature["read"](self.before, self.context)
        self.assertIsNone(reason)
        proposal, reason = self.feature["propose"](view,
            lua_table(self.h.lua, {"enabled": True,
                "policy": "Balanced"}))
        self.assertIsNone(reason)
        return proposal

    def test_unbound_display_upgrade(self):
        proposal = self.plan()
        self.assertEqual(proposal["intent"]["cosmeticKind"], "background")
        self.assertEqual(proposal["intent"]["itemId"], "bg_new")
        baseline, reason = self.feature["capture"](proposal, self.before)
        self.assertIsNone(reason)
        after = self.h.snapshot(revision=2, native={"fullSync": True,
            "equippedBackground": "bg_new", "inventory": {
                "bg_old": 1, "bg_new": 1}, "inventoryBound": {},
            "collectionBound": {}})
        self.assertEqual(self.feature["evaluate"](proposal, self.before,
            after, lua_table(self.h.lua, {"ok": True}), baseline),
            "confirmed")

    def test_bound_custody_or_changed_worn_blocks(self):
        proposal = self.plan()
        self.before["native"]["equippedBackground"] = None
        self.assertIsNone(self.feature["capture"](proposal, self.before)[0])
        self.before["native"]["equippedBackground"] = "bg_old"
        self.before["native"]["inventoryBound"]["bg_new"] = 1
        self.assertIsNone(self.feature["read"](self.before,
            self.context)[0])

    def test_missing_send_time_snapshot_fails_closed(self):
        proposal = self.plan()
        self.assertIsNone(self.feature["capture"](proposal, None)[0])

    def test_transient_or_changed_negative_reply_keeps_cosmetic_custody(self):
        proposal=self.plan()
        baseline,_=self.feature.capture(proposal,self.before)
        for code in ('busy','presence','rate_limited'):
            with self.subTest(code=code):
                after=self.h.snapshot(revision=2,native=self.before.native)
                self.assertEqual(self.feature.evaluate(proposal,self.before,after,
                    lua_table(self.h.lua,{'ok':False,'code':code}),baseline),'pending')
        for worn,amount,full,expected in [('bg_old',1,True,'rejected'),('bg_new',1,True,'pending'),
                ('bg_old',0,True,'pending'),('bg_old',1,False,'pending')]:
            with self.subTest(worn=worn,amount=amount,full=full):
                after=self.h.snapshot(revision=2,native={'fullSync':full,'equippedBackground':worn,
                    'inventory':{'bg_old':1,'bg_new':amount},'inventoryBound':{},'collectionBound':{}})
                self.assertEqual(self.feature.evaluate(proposal,self.before,after,
                    lua_table(self.h.lua,{'ok':False}),baseline),expected)
        after=self.h.snapshot(revision=2,native={'fullSync':True,'equippedBackground':'bg_new'})
        self.assertEqual(self.feature.evaluate(proposal,self.before,after,
            lua_table(self.h.lua,{'ok':True,'pending':True}),baseline),'pending')


if __name__ == "__main__":
    unittest.main()
