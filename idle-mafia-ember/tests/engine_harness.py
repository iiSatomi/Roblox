"""Deterministic Lua broker harness; transport never reaches Roblox."""
from pathlib import Path

from lupa import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]


def lua_table(lua, value):
    if isinstance(value, dict):
        return lua.table_from({k: lua_table(lua, v) for k, v in value.items()})
    if isinstance(value, list):
        return lua.table_from([lua_table(lua, v) for v in value])
    return value


class Harness:
    def __init__(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals().testNow = 0.0
        self.contracts = self.load("src/engine/Contracts.luau")
        clock_module = self.load("src/engine/Clock.luau")
        journal_module = self.load("src/engine/Journal.luau")
        broker_module = self.load("src/engine/Broker.luau")
        self.clock = clock_module.new(self.lua.eval("function() return testNow end"))
        self.transport = self.lua.execute("""
            return { sent = {}, callbacks = {}, Send = function(self, proposal, callback)
                self.sent[#self.sent + 1] = proposal
                self.callbacks[#self.callbacks + 1] = callback
            end }
        """)
        self.journal = journal_module.new(100)
        self.session = {
            "session": "run-a", "account": "user-a", "place": "73897506680154",
            "release": "release-a",
        }
        self.policy = lua_table(self.lua, {
            "contracts": self.contracts, "session": self.session,
            "maxSnapshotAge": 2, "cooldownSeconds": 45,
        })
        self.policy["confirm"] = self.lua.eval("""
            function(proposal, before, after, reply)
                if after.proofKey == proposal.actionKey
                    and after.revision > before.revision then
                    return "confirmed"
                end
                if after.rejectionKey == proposal.actionKey then return "rejected" end
                return "pending"
            end
        """)
        self.broker = broker_module.new(
            self.clock, self.transport, self.journal, self.policy
        )

    def load(self, relative):
        return self.lua.execute((ROOT / relative).read_text(encoding="utf-8"))

    def at(self, value):
        self.lua.globals().testNow = value

    def snapshot(self, revision=1, captured_at=None, **changes):
        value = {
            **self.session, "revision": revision,
            "capturedAt": self.lua.globals().testNow if captured_at is None else captured_at,
        }
        value.update(changes)
        return lua_table(self.lua, value)

    def proposal(self, feature="jobs", key="jobs:j_watch:1", revision=1):
        return lua_table(self.lua, {
            **self.session, "revision": revision, "feature": feature,
            "actionKey": key, "resources": {"energy": 1},
            "intent": {"kind": "job" if feature == "jobs" else "operation", "targetId": key},
        })

    def events(self):
        return self.journal.Events(self.journal)
