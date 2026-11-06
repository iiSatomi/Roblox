"""Current client source identity must match the reviewed place release."""
import unittest

from engine_harness import Harness, lua_table


class CompatibilityGateTests(unittest.TestCase):
    def test_exact_place_version_and_fingerprint(self):
        h = Harness()
        observer = h.lua.execute("""return {
            Read = function() return {
                place = '73897506680154', gameVersion = '0.26.530',
                account = 'user-a',
                fingerprint = string.rep('A', 64),
            } end,
        }""")
        gate = h.load("src/transport/CompatibilityGate.luau").new(
            lua_table(h.lua, {"place": "73897506680154",
                "account": "user-a",
                "gameVersion": "0.26.530",
                "fingerprint": "a" * 64}), observer)
        self.assertTrue(gate.Verify(gate)[0])
        observer["Read"] = h.lua.eval("""function()
            return { place = '73897506680154',
                account = 'user-b', gameVersion = '0.26.530',
                fingerprint = string.rep('a', 64) }
        end""")
        self.assertFalse(gate.Verify(gate)[0])
        observer["Read"] = h.lua.eval("""function()
            return { place = '73897506680154',
                account = 'user-a',
                gameVersion = '0.26.530',
                fingerprint = string.rep('b', 64) }
        end""")
        self.assertFalse(gate.Verify(gate)[0])


if __name__ == "__main__":
    unittest.main()
