"""Native call names resolve to current RemoteFunctions at dispatch time."""
import unittest

from engine_harness import Harness


class NativeRemoteResolverTests(unittest.TestCase):
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
