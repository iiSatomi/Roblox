-- Confirmed earned payouts only. No remote, reset, budget or replay capability.
local Ledger, Methods, writers = {}, {}, {}
Methods.__index = Methods
local MAX = 9007199254740991
local function integer(v, low) return type(v) == "number" and v == v and v >= low and v <= MAX and v % 1 == 0 end
local function text(v) return type(v) == "string" and #v > 0 and #v <= 1000 end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not equal(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end
local function copy(raw, scope)
    if type(raw) ~= "table" or raw.version ~= 1 or not integer(raw.claims, 0)
        or not integer(raw.gold, 0) or not integer(raw.lastRequestId, 0)
        or type(raw.recent) ~= "table" or #raw.recent > 32 then return nil end
    for _, field in ipairs({"account", "place", "release"}) do if raw[field] ~= scope[field] then return nil end end
    local out = {version = 1, account = scope.account, place = scope.place, release = scope.release,
        claims = raw.claims, gold = raw.gold, lastRequestId = raw.lastRequestId, recent = {}}
    local sum, lastId = 0, 0
    for index, row in ipairs(raw.recent) do
        if type(row) ~= "table" or not integer(row.requestId, lastId + 1)
            or not text(row.actionKey) or not text(row.session) or not integer(row.revision, 0)
            or not integer(row.earnings, 1) or not integer(row.goldBefore, 0)
            or not integer(row.goldAfter, 0) or row.goldAfter ~= row.goldBefore + row.earnings then return nil end
        if row.serverNow ~= nil and (type(row.serverNow) ~= "number" or row.serverNow ~= row.serverNow
            or row.serverNow < 0 or row.serverNow > MAX) then return nil end
        local result = {}
        for key, value in pairs(row) do
            if key ~= "requestId" and key ~= "actionKey" and key ~= "session" and key ~= "revision"
                and key ~= "earnings" and key ~= "goldBefore" and key ~= "goldAfter" and key ~= "serverNow" then return nil end
            result[key] = value
        end
        out.recent[index], lastId, sum = result, row.requestId, sum + row.earnings
    end
    for key in pairs(raw.recent) do if not integer(key, 1) or key > #out.recent then return nil end end
    if lastId ~= raw.lastRequestId or raw.claims > raw.lastRequestId
        or #out.recent ~= math.min(raw.claims, 32) or raw.gold < sum
        or (raw.claims == #out.recent and raw.gold ~= sum)
        or (raw.claims > 0 and #out.recent == 0) then return nil end
    for key in pairs(raw) do if out[key] == nil then return nil end end
    return out
end

function Ledger.new(storage, scope, evidence)
    if type(storage) ~= "table" or storage.strictRecovery ~= true or type(storage.Read) ~= "function"
        or type(storage.Write) ~= "function" or type(scope) ~= "table" or type(evidence) ~= "table"
        or type(evidence.recoverSaved) ~= "function" then return nil, "Payout ledger dependencies unavailable" end
    local own, key = {}, "idle-mafia-ember:payouts:v1:"
    for _, field in ipairs({"account", "place", "release"}) do
        if not text(scope[field]) or #scope[field] > 120 then return nil, "Invalid payout scope" end
        own[field], key = scope[field], key .. #scope[field] .. ":" .. scope[field]
    end
    if writers[key] then return nil, "Payout ledger save in flight" end
    local ok, raw = pcall(storage.Read, storage, key)
    if not ok then return nil, "Payout ledger read failed" end
    local value = raw and copy(raw, own) or nil
    if raw ~= nil and not value then return nil, "Corrupt payout ledger" end
    local state = value or {version = 1, account = own.account, place = own.place, release = own.release,
        claims = 0, gold = 0, lastRequestId = 0, recent = {}}
    return setmetatable({storage = storage, scope = own, key = key, evidence = evidence,
        state = state, expected = value, closed = false}, Methods), nil
end
function Methods:Summary() return copy(self.state, self.scope) end
function Methods:Close() self.closed = true end
function Methods:Record(data, after)
    if self.closed or self.evidence.recoverSaved(data, after) ~= "confirmed" then return false, "Exact confirmed payout required" end
    local proposal, baseline = data.proposal, data.baseline
    for _, field in ipairs({"account", "place", "release"}) do
        if proposal[field] ~= self.scope[field] then return false, "Payout scope changed" end
    end
    local id = proposal.requestId
    if not integer(id, 1) or not text(proposal.actionKey) then return false, "Numbered payout required" end
    local row = {requestId = id, actionKey = proposal.actionKey, session = after.session, revision = after.revision,
        earnings = baseline.earnings, goldBefore = baseline.gold, goldAfter = baseline.gold + baseline.earnings,
        serverNow = after.native and after.native.serverNow}
    if writers[self.key] then return false, "Payout ledger save in flight" end
    writers[self.key] = self
    local ok, saved = pcall(function()
        local raw = self.storage:Read(self.key)
        local current = raw and copy(raw, self.scope) or nil
        if (raw ~= nil and not current) or not equal(current, self.expected) or self.closed then return false end
        if id <= self.state.lastRequestId then
            local last = self.state.recent[#self.state.recent]
            if id ~= self.state.lastRequestId or not last then return false end
            for _, field in ipairs({"requestId", "actionKey", "earnings", "goldBefore", "goldAfter"}) do
                if row[field] ~= last[field] then return false end
            end
            return true -- Later observation time/session is not a new payout.
        end
        local nextState = copy(self.state, self.scope)
        if nextState.claims >= MAX or nextState.gold > MAX - baseline.earnings then return false end
        nextState.claims, nextState.gold, nextState.lastRequestId = nextState.claims + 1, nextState.gold + baseline.earnings, id
        if #nextState.recent == 32 then table.remove(nextState.recent, 1) end
        nextState.recent[#nextState.recent + 1] = row
        nextState = copy(nextState, self.scope)
        if not nextState or self.storage:Write(self.key, nextState) == false then return false end
        self.state, self.expected = nextState, copy(nextState, self.scope)
        return not self.closed
    end)
    if writers[self.key] == self then writers[self.key] = nil end
    return ok and saved == true, (not ok or saved ~= true) and "Payout ledger save refused" or nil
end
return Ledger
