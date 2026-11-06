"""One bounded cumulative native browse observation replaces prior rows."""
import unittest
from engine_harness import Harness, lua_table


class MarketBrowsePagesTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness()
        self.module=self.h.load('src/tabs/blackMarket/MarketBrowsePages.luau')
        self.pages=self.module.new(5,500)

    def row(self,key,price=10):
        return {'id':key,'item':'w_baton','qty':1,'price':price,'mine':False}

    def reply(self,rows,**changes):
        data={'kind':'item','arg':'w_baton','page':5,'pages':5,'capturedAt':10,
            'more':False,'stale':False,'small':False,'rows':rows}
        data.update(changes)
        return lua_table(self.h.lua,data)

    def test_independent_cumulative_refresh_replaces_rows_and_can_observe_changed_prices(self):
        self.assertEqual(self.pages.Begin(self.pages,'item','w_baton')[0].page,5)
        _,first,reason=self.pages.Accept(self.pages,self.reply([self.row('a'),self.row('b')]))
        self.assertIsNone(reason);self.assertEqual(len(first.rows),2)
        self.pages.Begin(self.pages,'item','w_baton')
        _,second,reason=self.pages.Accept(self.pages,self.reply([self.row('a',11)],capturedAt=30,pages=1))
        self.assertIsNone(reason)
        self.assertEqual((len(second.rows),second.rows[1].price,second.pages),(1,11,1))
        self.assertEqual((len(first.rows),first.rows[1].price),(2,10))

    def test_duplicate_rows_wrong_scope_budget_and_malformed_metadata_fail_closed(self):
        for changes in ({'rows':[self.row('a'),self.row('a',11)]},{'arg':'other'},
            {'page':4},{'pages':6},{'small':'true'},{'capturedAt':float('nan')}):
            with self.subTest(changes=changes):
                self.pages.Begin(self.pages,'item','w_baton')
                data={'rows':[self.row('a')],**changes}
                self.assertIsNone(self.pages.Accept(self.pages,self.reply(**data))[1])

    def test_page_and_row_caps_preserve_honest_partial_metadata(self):
        pages=self.module.new(2,1)
        self.assertEqual(pages.Begin(pages,'item','w_baton')[0].page,2)
        _,partial,reason=pages.Accept(pages,self.reply([self.row('a')],page=2,pages=2,more=True,small=True))
        self.assertIsNone(reason);self.assertTrue(partial.more);self.assertTrue(partial.small)
        pages.Begin(pages,'item','w_baton')
        self.assertIsNone(pages.Accept(pages,self.reply([self.row('a'),self.row('b')],page=2,pages=2))[1])
        pages.Close(pages)
        self.assertIsNone(pages.Begin(pages,'item','w_baton')[0])

    def test_all_scope_keeps_nil_argument_and_sparse_rows_are_rejected(self):
        self.assertIsNone(self.pages.Begin(self.pages,'all','w_baton')[0])
        scope=self.pages.Begin(self.pages,'all',None)[0]
        self.assertEqual(scope.kind,'all');self.assertIsNone(scope.arg)
        reply=self.reply([self.row('a')],kind='all',arg=None)
        reply.rows[3]=lua_table(self.h.lua,self.row('b'))
        self.assertIsNone(self.pages.Accept(self.pages,reply)[1])


if __name__=='__main__': unittest.main()
