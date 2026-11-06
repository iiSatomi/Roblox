import unittest
from engine_harness import Harness,lua_table

class AllianceTabTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();h=self.h
        h.lua.globals().allianceModule=h.load('src/tabs/alliance/Module.luau')
        h.lua.globals().ember=h.load('tests/ember_double.lua')()
        h.lua.execute("""
        alive=true; values={['alliance.allies']='', ['alliance.enemies']='', ['alliance.mode']='Off', ['alliance.browse']=false, ['alliance.query']=''}
        handles={}; changes=0
        function change(k,v) changes=changes+1;values[k]=v end
        function bind(c,kind,key,o) o.Callback=function(v) if alive then change(key,v) end end;local h=c[kind](c,o);handles[key]=h;return h end
        window=ember.new({Name='AllianceTest'}); tab=allianceModule.new(window:Section('Alliance/Enemy'),bind,change,function() return alive end,
            function(o) return not o or not(o.initial or o.restored or o.reverted) end)
        model={values=values,automationRuntime={familyDirectory={query='',ready=true,capturedAt=0,rows={{id='family-a',name='Same'},{id='family-b',name='Same'}}}}}
        tab:Render(model)
        """)
        self.tab=h.lua.globals().tab
    def runlua(self,s):return self.h.lua.execute(s)
    def test_subtabs_and_same_name_picker_preserve_id_identity(self):
        self.assertTrue(self.tab.panels.allies.visible);self.assertFalse(self.tab.panels.enemies.visible)
        self.tab.switches.enemies.Click(self.tab.switches.enemies);self.runlua('ember.Flush()')
        self.assertFalse(self.tab.panels.allies.visible);self.assertTrue(self.tab.panels.enemies.visible)
        self.runlua("tab.picker:Set('Same [family-b]',true);tab.add.enemies:Click();ember.Flush();tab:Render(model)")
        self.assertEqual(self.runlua("return values['alliance.enemies']"),'family-b')
        self.assertEqual(self.runlua("return values['alliance.allies']"),'')
    def test_adding_and_explicit_removal_do_not_lose_hidden_entries(self):
        self.runlua("values['alliance.allies']='outside';tab:Render(model);tab.picker:Set('Same [family-a]',true);tab.add.allies:Click();ember.Flush();tab:Render(model)")
        self.assertEqual(self.runlua("return values['alliance.allies']"),'outside,family-a')
        self.runlua("tab.saved.allies:Set('outside',true);tab.remove.allies:Click();ember.Flush()")
        self.assertEqual(self.runlua("return values['alliance.allies']"),'family-a')
    def test_query_change_hides_old_results_and_unload_fences_queued_edit(self):
        self.runlua("values['alliance.query']='changed';tab:Render(model)")
        self.assertEqual(len(self.tab.picker.options.Options),0)
        self.runlua("values['alliance.query']='';tab:Render(model);tab.picker:Set('Same [family-a]',true);tab.add.allies:Click();alive=false;ember.Flush()")
        self.assertEqual(self.runlua("return values['alliance.allies']"),'')
    def test_empty_partial_and_missing_directory_are_honest(self):
        self.runlua('model.automationRuntime.familyDirectory=nil;tab:Render(model)')
        self.assertIn('Unavailable',self.tab.status.Get(self.tab.status))
        self.runlua("model.automationRuntime.familyDirectory={query='',ready=false,rows={}};tab:Render(model)")
        self.assertIn('Partial',self.tab.status.Get(self.tab.status))
