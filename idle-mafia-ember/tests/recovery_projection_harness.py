"""Shared tests for real capture dependencies, never a production substitute."""
from engine_harness import lua_table


def assert_projection(test, h, evidence, proposal, before):
    baseline, reason = evidence.capture(proposal, before)
    test.assertIsNone(reason)
    before.data = before.native
    before.unusedSelectionCatalog = lua_table(h.lua,[
        {"id":f"unused_{i}","label":"x"*200,"capacity":5} for i in range(1500)])
    pending = h.load("src/storage/PendingAction.luau")
    encoded, reason = pending.Capture(proposal, before, baseline)
    test.assertIsNone(reason)
    decoded = pending.Decode(encoded)
    test.assertIsNotNone(decoded)
    test.assertIsNone(decoded.before.data)
    test.assertIsNone(decoded.before.unusedSelectionCatalog)
    equal = h.lua.eval("""function(a,b)
        local function eq(x,y)
            if type(x)~=type(y) then return false end
            if type(x)~='table' then return x==y end
            for k,v in pairs(x) do if not eq(v,y[k]) then return false end end
            for k in pairs(y) do if x[k]==nil then return false end end
            return true
        end
        return eq(a,b)
    end""")
    test.assertTrue(equal(before.native,decoded.before.native))
    recaptured,reason = evidence.capture(decoded.proposal,decoded.before)
    test.assertIsNone(reason)
    test.assertTrue(equal(baseline,recaptured))
    recoded,reason = pending.Capture(decoded.proposal,decoded.before,recaptured)
    test.assertIsNone(reason)
    test.assertTrue(pending.Same(encoded,recoded))
    copied,reason = pending.Copy(encoded)
    test.assertIsNone(reason)
    test.assertTrue(pending.Same(encoded,copied))
    return decoded
