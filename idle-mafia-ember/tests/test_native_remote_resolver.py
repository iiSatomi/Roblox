"""Native call names resolve to current RemoteFunctions at dispatch time."""
import unittest

from engine_harness import Harness


class NativeRemoteResolverTests(unittest.TestCase):
    def test_all_native_calls_share_one_invocation_lane(self):
        h = Harness()
        folder = h.lua.execute("""local folder = { children = {} }
            function folder:FindFirstChild(name) return self.children[name] end
            local remote = { Parent = folder, nested = true }
            function remote:IsA(kind) return kind == 'RemoteFunction' end
            function remote:InvokeServer()
                if self.nested then
                    self.nested = false
                    local ok, reason = pcall(function()
                        return resolver:Invoke('DoJob')
                    end)
                    return { nestedOk = ok, nestedReason = tostring(reason) }
                end
                if self.fail then error('remote interrupted') end
                return { ok = true }
            end
            folder.children.DoJob = remote
            return folder
        """)
        module = h.load("src/transport/NativeRemoteResolver.luau")
        resolver, _ = module.new(folder)
        h.lua.globals().resolver = resolver
        first = resolver.Invoke(resolver, "DoJob")
        self.assertFalse(first["nestedOk"])
        self.assertIn("already running", first["nestedReason"])
        folder.children.DoJob.fail = True
        with self.assertRaises(Exception):
            resolver.Invoke(resolver, "DoJob")
        folder.children.DoJob.fail = False
        self.assertTrue(resolver.Invoke(resolver, "DoJob")["ok"])

    def test_exact_arguments_and_replaced_remote_fail_closed(self):
        h = Harness()
        folder = h.lua.execute("""local folder = { children = {} }
            function folder:FindFirstChild(name)
                return self.children[name]
            end
            local remote = { Parent = folder }
            function remote:IsA(kind)
                return kind == 'RemoteFunction'
            end
            function remote:InvokeServer(...)
                return table.pack(...)
            end
            folder.children.BossAction = remote
            return folder
        """)
        module = h.load(
            "src/transport/NativeRemoteResolver.luau")
        resolver, reason = module.new(folder)
        self.assertIsNone(reason)
        args = resolver.Invoke(resolver, "BossAction",
                               "shopBuy", "w_policebaton", None)
        self.assertEqual(args["n"], 3)
        self.assertIsNone(args[3])
        folder.children.BossAction.Parent = None
        with self.assertRaises(Exception):
            resolver.Invoke(resolver, "BossAction", "attack")
        resolver.Close(resolver)
        with self.assertRaises(Exception):
            resolver.Invoke(resolver, "BossAction", "attack")

    def test_invalid_folder_or_name_blocks(self):
        h = Harness()
        module = h.load(
            "src/transport/NativeRemoteResolver.luau")
        self.assertIsNone(module.new(h.lua.table())[0])
        folder = h.lua.execute("""return {
            FindFirstChild = function() return nil end,
        }""")
        resolver, _ = module.new(folder)
        with self.assertRaises(Exception):
            resolver.Invoke(resolver, "../Other", 1)
        with self.assertRaises(Exception):
            resolver.Invoke(resolver, "DoJob", 1)


if __name__ == "__main__":
    unittest.main()


class NativeRemoteLinkResolverTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness()
        self.folder,self.link=self.h.lua.execute("""local folder={children={},calls=0}
            function folder:FindFirstChild(name) return self.children[name] end
            local remote={Parent=folder,Name='Attack',IsA=function(_,kind) return kind=='RemoteFunction' end}
            function remote:InvokeServer(...) folder.calls=folder.calls+1;return table.pack(...) end
            folder.children.Attack=remote
            local wrapped={Name='Attack',Instance=remote}
            function wrapped:InvokeServer(...) return remote:InvokeServer('fixture-native-header',...) end
            local link={valid=true,wrapped=wrapped}
            function link:Current() return self.valid end
            function link:Resolve(name) return self.wrapped end
            return folder,link""")
        self.module=self.h.load('src/transport/NativeRemoteResolver.luau')
    def test_current_game_wrapper_supplies_its_opaque_header_and_preserves_nil_arguments(self):
        resolver,why=self.module.new(self.folder,None,self.link);self.assertIsNone(why)
        args=resolver.Invoke(resolver,'Attack',42,None)
        self.assertEqual(args.n,3);self.assertEqual(args[1],'fixture-native-header')
        self.assertEqual(args[2],42);self.assertIsNone(args[3]);self.assertEqual(self.folder.calls,1)
    def test_changed_wrapper_instance_or_name_never_calls_the_raw_function(self):
        resolver=self.module.new(self.folder,None,self.link)[0]
        self.link.wrapped.Instance=self.h.lua.table()
        with self.assertRaises(Exception):resolver.Invoke(resolver,'Attack',42)
        self.assertEqual(self.folder.calls,0)
    def test_changed_native_link_cannot_fall_back_to_raw_protocol(self):
        resolver=self.module.new(self.folder,None,self.link)[0];self.link.valid=False
        with self.assertRaises(Exception):resolver.Invoke(resolver,'Attack',42)
        self.assertEqual(self.folder.calls,0)
    def test_native_exemption_returns_the_same_raw_instance_without_added_arguments(self):
        self.link.wrapped=self.folder.children.Attack
        resolver=self.module.new(self.folder,None,self.link)[0]
        args=resolver.Invoke(resolver,'Attack',42)
        self.assertEqual(args.n,1);self.assertEqual(args[1],42)

    def test_replaced_wrapper_callable_or_lookup_cannot_execute_new_code(self):
        resolver=self.module.new(self.folder,None,self.link)[0]
        resolver.Invoke(resolver,'Attack',42)
        self.link.wrapped.InvokeServer=self.h.lua.eval("function() error('changed-code-executed') end")
        with self.assertRaisesRegex(Exception,'wrapper.*changed'):
            resolver.Invoke(resolver,'Attack',42)
        self.assertEqual(self.folder.calls,1)
    def test_changed_lookup_is_fenced_before_it_runs(self):
        resolver=self.module.new(self.folder,None,self.link)[0]
        self.link.Resolve=self.h.lua.eval("function() error('changed-lookup-executed') end")
        with self.assertRaisesRegex(Exception,'link.*changed'):
            resolver.Invoke(resolver,'Attack',42)
        self.assertEqual(self.folder.calls,0)

    def test_read_reply_from_retired_native_link_is_not_published(self):
        lane=self.h.load('src/engine/RequestLane.luau').new(self.h.clock)
        token=lane.TryAcquire(lane,'read','read:targets',5)[0]
        self.folder.children.GetHitList=self.folder.children.Attack
        self.link.wrapped.Name='GetHitList'
        self.h.lua.globals().retiringLink=self.link
        self.folder.children.GetHitList.InvokeServer=self.h.lua.eval('function() retiringLink.valid=false;return {ok=true,list={}} end')
        resolver=self.module.new(self.folder,lane,self.link)[0]
        with self.assertRaisesRegex(Exception,'source.*changed|RemoteLink.*unavailable'):
            resolver.InvokeOwned(resolver,token,'GetHitList',False)
    def test_current_source_probe_is_read_only_and_pins_existing_wrapper(self):
        resolver=self.module.new(self.folder,None,self.link)[0]
        self.assertTrue(resolver.Current(resolver,'Attack'));self.assertEqual(self.folder.calls,0)
        self.link.valid=False;self.assertFalse(resolver.Current(resolver,'Attack'))
