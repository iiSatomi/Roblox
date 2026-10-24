"""Saved Sync and State.onChanged subscriptions remain distinct."""
import unittest

from engine_harness import Harness


class NativeEventAdapterTests(unittest.TestCase):
    def test_current_folder_requires_direct_sync_remote_event(self):
        h = Harness()
        adapter = h.load("src/transport/NativeEventAdapter.luau")
        folder = h.lua.execute("""local folder = { children = {} }
            function folder:FindFirstChild(name)
                return self.children[name]
            end
            local signal = { Connect = function() return {
                Disconnect = function() end } end }
            folder.children.Sync = {
                Parent = folder, OnClientEvent = signal,
                IsA = function(_, kind) return kind == 'RemoteEvent' end,
            }
            return folder""")
        state = h.lua.execute("""return {
            onChanged = function() return {
                Disconnect = function() end } end,
        }""")
        self.assertIsNotNone(adapter.fromFolder(folder, state)[0])
        folder["children"]["Sync"]["Parent"] = None
        self.assertIsNone(adapter.fromFolder(folder, state)[0])

    def test_subscriptions_forward_and_disconnect(self):
        h = Harness()
        signal = h.lua.execute("""return {
            callback = nil, disconnected = false,
            Connect = function(self, callback)
                self.callback = callback
                return { Disconnect = function()
                    self.disconnected = true
                end }
            end,
        }""")
        state = h.lua.execute("""return {
            callback = nil, disconnected = false,
            onChanged = function(callback)
                state.callback = callback
                return { Disconnect = function()
                    state.disconnected = true
                end }
            end,
        }""")
        h.lua.globals().state = state
        adapter = h.load(
            "src/transport/NativeEventAdapter.luau")
        events, reason = adapter.new(signal, state)
        self.assertIsNone(reason)
        seen = []
        sync = events.SubscribeSync(events,
            h.lua.eval("function(value) record('sync', value) end"))
        changed = events.SubscribeChanged(events,
            h.lua.eval("function(value) record('changed', value) end"))
        h.lua.globals().record = lambda kind, value: seen.append((kind, value))
        signal.callback("one")
        state.callback("two")
        self.assertEqual(seen, [("sync", "one"), ("changed", "two")])
        sync.Disconnect(sync)
        changed.Disconnect(changed)
        self.assertTrue(signal.disconnected)
        self.assertTrue(state.disconnected)


if __name__ == "__main__":
    unittest.main()
