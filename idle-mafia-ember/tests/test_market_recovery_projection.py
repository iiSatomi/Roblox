"""Market durable recapture uses complete native custody, without research catalogs."""
import unittest
from engine_harness import Harness, lua_table
from recovery_projection_harness import assert_projection


class MarketRecoveryProjectionTests(unittest.TestCase):
    def test_real_sell_withdraw_buy_and_followup_list_baselines_roundtrip(self):
        cases=(('marketSell','marketList','MarketListEvidence'),
               ('marketSell','marketCollectionWithdraw','MarketCollectionWithdrawEvidence'),
               ('marketFlip','marketBuy','MarketBuyEvidence'),
               ('marketFlip','marketList','MarketListEvidence'))
        for feature,kind,module in cases:
            with self.subTest(feature=feature,kind=kind):
                h=Harness()
                before=h.snapshot(native={'fullSync':True,'serverNow':100,
                    'inventory':{'item_a':2,'gold_bar':10},'inventoryBound':{},
                    'collection':{'item_a':3},'collectionBound':{},'market':{'listings':{}}})
                proposal=h.proposal(feature=feature,key=feature+':owned:1')
                intent={'kind':kind,'itemId':'item_a','quantity':1,'ask':2}
                if kind=='marketCollectionWithdraw':
                    intent.update(checkpointFloor=1,collectionBefore=3,looseBefore=2)
                if kind=='marketBuy':
                    intent.update(listingId='foreign-a',quotedPrice=2)
                proposal.intent=lua_table(h.lua,intent)
                proposal.resources=lua_table(h.lua,{'gold_bar':2} if kind=='marketBuy' else
                    {} if kind=='marketCollectionWithdraw' else {'item_a':1})
                selected=h.load('src/tabs/blackMarket/'+module+'.luau')
                # Production MarketSellRuntime.recoverSaved restores this flag
                # only for recapture; PendingAction must never persist a replay arm.
                capture=h.lua.eval('''function(selected,preflight)
                    return {capture=function(p,before)
                        local input={} for k,v in pairs(p) do input[k]=v end
                        if preflight then input.preflightOnly=true end
                        return selected.capture(input,before)
                    end}
                end''')(selected,kind!='marketList' or feature=='marketFlip')
                decoded=assert_projection(self,h,capture,proposal,before)
                self.assertIsNone(decoded.proposal.preflightOnly)
                self.assertEqual(decoded.before.native.inventory.gold_bar,10)
                self.assertEqual(decoded.before.native.collection.item_a,3)
                self.assertIsNotNone(decoded.before.native.market.listings)


if __name__=='__main__': unittest.main()
