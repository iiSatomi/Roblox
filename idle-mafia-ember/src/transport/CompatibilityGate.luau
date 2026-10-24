-- Compare current read-only client identity with the reviewed source release.
local CompatibilityGate = {}
local Methods = {}
Methods.__index = Methods

local function fingerprint(value)
    return type(value) == "string" and #value == 64
        and value:match("^[%x]+$") ~= nil
end

function CompatibilityGate.new(expected, observer)
    assert(type(expected) == "table"
        and type(expected.place) == "string"
        and #expected.place > 0
        and type(expected.account) == "string"
        and #expected.account > 0
        and type(expected.gameVersion) == "string"
        and #expected.gameVersion > 0
        and fingerprint(expected.fingerprint)
        and type(observer) == "table"
        and type(observer.Read) == "function",
        "Missing compatibility source")
    return setmetatable({ expected = {
        place = expected.place, account = expected.account,
        gameVersion = expected.gameVersion,
        fingerprint = expected.fingerprint:lower(),
    }, observer = observer }, Methods)
end

function Methods:Verify()
    local ok, actual = pcall(self.observer.Read, self.observer)
    if not ok or type(actual) ~= "table" then
        return false, "Current client identity unavailable"
    end
    if actual.place ~= self.expected.place then
        return false, "Current place differs from reviewed source"
    end
    if actual.account ~= self.expected.account then
        return false, "Current account differs from checkpoint scope"
    end
    if actual.gameVersion ~= self.expected.gameVersion then
        return false, "Current game version differs from reviewed source"
    end
    if not fingerprint(actual.fingerprint)
        or actual.fingerprint:lower()
            ~= self.expected.fingerprint then
        return false, "Current source fingerprint differs"
    end
    return true, nil
end

return CompatibilityGate
