"""Actual saved Market and Crew stores supply reservations without native calls."""
import unittest

from engine_harness import lua_table
import test_market_transactions as market_fixture
import test_crew_replacement as crew_fixture
import test_collection_donate as collection_fixture


class DurableReservationOwnersTests(unittest.TestCase):
    def market(self):
        fixture = market_fixture.MarketTransactionsTests()
        fixture.setUp()
        return fixture

    def test_saved_listing_blocks_two_copy_donation_but_allows_spare_after_restart(self):
        f = self.market()
        tx, _ = f.module.new(f.storage, f.scope, f.list_evidence)
        self.assertTrue(tx.PrepareOwnedList(tx, f.list_proposal(), f.list_raw())[0])
        tx, _ = f.module.new(f.storage, f.scope, f.list_evidence)
        f.h.lua.globals().savedMarket = tx
        owner = f.h.load("src/engine/ResourceReservations.luau").new(f.scope,
            f.h.lua.eval("function() return {} end"),
            f.h.lua.execute("return {{id='market',read=function() return savedMarket:ReservationClaims() end}}"))
        raw = f.list_raw(loose=3)
        proposal = f.h.proposal("collectionDonate", "deposit")
        proposal.resources = lua_table(f.h.lua, {"w_baton": 2})
        proposal.intent = lua_table(f.h.lua, {"kind": "collectionDonate", "itemId": "w_baton", "amount": 2})
        self.assertIsNone(owner.Check(owner, proposal, raw)[0])
        proposal.intent.amount, proposal.resources.w_baton = 1, 1
        self.assertIsNotNone(owner.Check(owner, proposal, raw)[0])
        tx.MarkSending(tx)
        exact = f.list_raw(revision=2, loose=3, listings={"L1": f.listing()}, now=1002)
        self.assertEqual(tx.Reconcile(tx, exact)[0], "observed")
        self.assertIsNone(tx.ReservationClaims(tx))

    def test_unconfirmed_rental_keeps_loose_gold_and_observed_rental_releases_it(self):
        f = self.market()
        f.tx.PrepareRent(f.tx, f.proposal(), f.raw())
        f.tx.MarkSending(f.tx)
        tx, _ = f.module.new(f.storage, f.scope)
        claims, reason = tx.ReservationClaims(tx)
        self.assertIsNone(reason)
        self.assertEqual(claims.claims["items"]["L:gold_bar"], 1)
        self.assertEqual(tx.Reconcile(tx, f.raw(revision=2, loose=7, until=44200, now=1002))[0], "observed")
        self.assertIsNone(tx.ReservationClaims(tx))

    def test_market_source_refuses_mutated_saved_custody(self):
        f = self.market()
        f.tx.PrepareRent(f.tx, f.proposal(), f.raw())
        f.tx.transaction.cost = -1
        claims, reason = f.tx.ReservationClaims(f.tx)
        self.assertIsNone(claims)
        self.assertIn("invalid", reason)

    def test_collection_preserves_spares_in_addition_to_market_reserved_copies(self):
        f = collection_fixture.CollectionDonateTests()
        f.setUp()
        f.before.native.inventory.w_a = 5
        producer = f.h.load("src/engine/CollectionProtection.luau")
        owner = f.h.lua.execute("return {Held=function() return {items={['L:w_a']=2},funds={},allItems=false} end}")
        proof, reason = producer.derive(f.before, f.context, f.h.lua.table(), f.h.lua.table(), owner)
        self.assertIsNone(reason)
        f.before.collectionProtection, f.context.collectionProtection = proof, proof
        proposal = f.plan()
        self.assertEqual(proposal.intent.amount, 1)
        self.assertEqual(proposal.intent.reserve, 4)
        self.assertIsNotNone(f.feature.capture(proposal, f.before)[0])

    def test_crew_replacement_reserves_funded_hire_until_exact_member_observed(self):
        f = crew_fixture.CrewReplacementTests()
        f.setUp()
        proposal, before = f.prepare()
        reservations = f.h.load("src/engine/ResourceReservations.luau")
        claims, reason = f.tx.ReservationClaims(f.tx, reservations)
        self.assertIsNone(reason)
        self.assertEqual(claims.claims.funds.cash, 10000)
        self.assertEqual(claims.actionKey, proposal.actionKey)
        self.assertTrue(claims.claims.members["slot:2"])
        restarted = f.restart()
        self.assertEqual(restarted.ReservationClaims(restarted, reservations)[0].claims.funds.cash, 10000)
