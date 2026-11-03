-- Exact settled outcomes survive checkpoint cleanup interruption; no gameplay calls.
local Ledger, Methods, writers = {}, {}, {}
Methods.__index = Methods
local MAX = 9007199254740991
local function number(v, low) return type(v) == "number" and v == v and v >= low and v <= MAX end
local function integer(v, low) return number(v, low) and v % 1 == 0 end
local function text(v) return type(v) == "string" and #v > 0 and #v <= 200 and not v:find("[%c]") end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not equal(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end
local HIGH, LOW, LOW_HITS, HIGH_LIMIT = 1000000000, 100000000, 3, 128
local HIGH_RULES, ACTION_RULES = "legacy-default-v1", "owned-action-rules-v1"
local function emptyHigh(last, version)
    return {version = version or 1, rules = version == 2 and ACTION_RULES or HIGH_RULES, lastRequestId = last, count = 0, overflow = false, targets = {}}
end
local function historyRow(row)
    return {requestId = row.requestId, at = row.initial.targetDaily.serverNow,
        cash = row.receipt.cashConfirmed, won = row.receipt.won}
end
local function updateHigh(memory, row, prior)
    memory.lastRequestId = row.requestId
    if row.feature ~= "combat" then return end
    if row.highPromoteCash ~= nil then memory.version, memory.rules = 2, ACTION_RULES end
    local promote, below, hits = row.highPromoteCash or HIGH, row.highDemoteBelow or LOW, row.highDemoteHits or LOW_HITS
    local key, cash = tostring(row.target), row.receipt.cashConfirmed
    local target = memory.targets[key]
    if not target and cash >= promote then
        if memory.count >= HIGH_LIMIT then memory.overflow = true; return end
        target = {userId = row.target, history = {}, lowStreak = 0}
        for _, previous in ipairs(prior) do
            if previous.feature == "combat" and previous.target == row.target then target.history[#target.history + 1] = historyRow(previous) end
        end
        memory.targets[key], memory.count = target, memory.count + 1
    end
    if not target then return end
    target.name, target.level, target.requestId = row.targetName, row.targetLevel, row.requestId
    if cash >= promote then
        target.lastHighCash, target.promotedAt, target.lowStreak = cash, row.initial.targetDaily.serverNow, 0
    else target.lowStreak = below > 0 and cash < below and target.lowStreak + 1 or 0 end
    if #target.history == 32 then table.remove(target.history, 1) end
    target.history[#target.history + 1] = historyRow(row)
    if target.lowStreak >= hits then memory.targets[key], memory.count = nil, memory.count - 1 end
end
local function deriveHigh(root)
    local memory, prior = emptyHigh(0), {}
    for _, row in ipairs(root.recent) do updateHigh(memory, row, prior); prior[#prior + 1] = row end
    memory.lastRequestId = root.lastRequestId
    return memory
end
local function onlyKeys(value, allowed)
    for key in pairs(value) do if not allowed[key] then return false end end
    return true
end
local function copyHigh(raw, root)
    if type(raw) ~= "table" or (raw.version ~= 1 and raw.version ~= 2)
        or raw.rules ~= (raw.version == 2 and ACTION_RULES or HIGH_RULES)
        or raw.lastRequestId ~= root.lastRequestId or type(raw.overflow) ~= "boolean"
        or not integer(raw.count, 0) or raw.count > HIGH_LIMIT or type(raw.targets) ~= "table"
        or not onlyKeys(raw, {version=true,rules=true,lastRequestId=true,count=true,overflow=true,targets=true}) then return nil end
    local result, count, cash, samples, seen = emptyHigh(raw.lastRequestId, raw.version), 0, 0, 0, {}
    result.overflow = raw.overflow
    local recent = {}; for _, row in ipairs(root.recent) do recent[row.requestId] = row end
    for key, target in pairs(raw.targets) do
        count = count + 1
        if count > HIGH_LIMIT or type(target) ~= "table" or not integer(target.userId, 1)
            or type(key) ~= "string" or key ~= tostring(target.userId) or not text(target.name) or #target.name > 64
            or not integer(target.level, 1) or not integer(target.requestId, 1) or target.requestId > root.lastRequestId
            or not integer(target.lastHighCash, raw.version == 2 and 1 or HIGH) or not number(target.promotedAt, 0)
            or not integer(target.lowStreak, 0) or target.lowStreak >= (raw.version == 2 and 100 or LOW_HITS)
            or type(target.history) ~= "table" or #target.history < 1 or #target.history > 32
            or not onlyKeys(target, {userId=true,name=true,level=true,requestId=true,lastHighCash=true,promotedAt=true,lowStreak=true,history=true}) then return nil end
        local copied = {userId=target.userId,name=target.name,level=target.level,requestId=target.requestId,
            lastHighCash=target.lastHighCash,promotedAt=target.promotedAt,lowStreak=target.lowStreak,history={}}
        local last = 0
        for index, item in ipairs(target.history) do
            if type(item) ~= "table" or not integer(item.requestId, last + 1) or item.requestId > target.requestId
                or seen[item.requestId] or not number(item.at, 0) or not integer(item.cash, 0) or type(item.won) ~= "boolean"
                or not onlyKeys(item, {requestId=true,at=true,cash=true,won=true}) then return nil end
            local owned = recent[item.requestId]
            if owned and (owned.feature ~= "combat" or owned.target ~= target.userId or owned.initial.targetDaily.serverNow ~= item.at
                or owned.receipt.cashConfirmed ~= item.cash or owned.receipt.won ~= item.won) then return nil end
            seen[item.requestId], last = true, item.requestId
            copied.history[index] = {requestId=item.requestId,at=item.at,cash=item.cash,won=item.won}
            cash, samples = cash + item.cash, samples + 1
        end
        for index in pairs(target.history) do if not integer(index, 1) or index > #target.history then return nil end end
        if last ~= target.requestId then return nil end
        local low = 0
        for index = #target.history, 1, -1 do
            if target.history[index].cash >= LOW then break end
            low = low + 1
        end
        if raw.version == 1 and low ~= target.lowStreak then return nil end
        if raw.version == 2 then
            -- The pre-window counter is unknown, not zero. Retained action-owned
            -- rules constrain the exact reachable range; resets/promotions make it exact.
            local minimum, maximum, active = 0, 99, true
            for _, owned in ipairs(root.recent) do
                if owned.feature == "combat" and owned.target == target.userId then
                    local promote, below, hits = owned.highPromoteCash or HIGH, owned.highDemoteBelow or LOW, owned.highDemoteHits or LOW_HITS
                    local cash = owned.receipt.cashConfirmed
                    if cash >= promote then minimum, maximum, active = 0, 0, true
                    elseif active then
                        if below > 0 and cash < below then
                            minimum, maximum = minimum + 1, math.min(maximum + 1, hits - 1)
                            if minimum >= hits then active = false end
                        else minimum, maximum = 0, 0 end
                    end
                end
            end
            if not active or target.lowStreak < minimum or target.lowStreak > maximum then return nil end
        end
        result.targets[key] = copied
    end
    if count ~= raw.count or samples > root.fights or cash > root.cash then return nil end
    -- Every retained ordinary settlement must be reflected in an existing tag's history.
    local latest = {}
    for _, row in ipairs(root.recent) do
        if row.feature == "combat" then
            local key = tostring(row.target)
            latest[key] = row
            if result.targets[key] and not seen[row.requestId] then return nil end
        end
    end
    for key, row in pairs(latest) do
        local target = result.targets[key]
        if target and (target.requestId ~= row.requestId or target.name ~= row.targetName or target.level ~= row.targetLevel) then return nil end
    end
    if not raw.overflow then
        for key, known in pairs(deriveHigh(root).targets) do
            local target = result.targets[key]
            if not target or target.lastHighCash ~= known.lastHighCash or target.promotedAt ~= known.promotedAt
                or target.lowStreak ~= known.lowStreak then return nil end
        end
    end
    result.count = count
    return result
end
local function copy(raw, scope, evidence)
    if type(raw) ~= "table" or raw.version ~= 1 or not integer(raw.fights, 0) or not integer(raw.wins, 0)
        or raw.wins > raw.fights or not integer(raw.cash, 0) or not integer(raw.stamina, 0)
        or raw.stamina < raw.fights or raw.stamina > raw.fights * 5 or not integer(raw.lastRequestId, 0)
        or raw.fights > raw.lastRequestId or type(raw.recent) ~= "table" or #raw.recent ~= math.min(raw.fights, 32) then return nil end
    local out = {version = 1, fights = raw.fights, wins = raw.wins, cash = raw.cash,
        stamina = raw.stamina, lastRequestId = raw.lastRequestId, recent = {}}
    for _, k in ipairs({"account", "place", "release"}) do
        if raw[k] ~= scope[k] then return nil end
        out[k] = scope[k]
    end
    local last, wins, cash, stamina, fights = 0, 0, 0, 0, {}
    for index, rawRow in ipairs(raw.recent) do
        local row = evidence.copyOutcome(rawRow)
        if not row or row.requestId <= last or fights[row.initial.fightId] then return nil end
        fights[row.initial.fightId] = true
        out.recent[index], last = row, row.requestId
        wins, cash, stamina = wins + (row.receipt.won and 1 or 0), cash + row.receipt.cashConfirmed, stamina + row.staminaCost
    end
    for k in pairs(raw.recent) do if not integer(k, 1) or k > #out.recent then return nil end end
    if raw.lastRequestId ~= last or raw.wins < wins or raw.cash < cash or raw.stamina < stamina
        or raw.fights == #out.recent and (raw.wins ~= wins or raw.cash ~= cash or raw.stamina ~= stamina) then return nil end
    if raw.highValue ~= nil then
        out.highValue = copyHigh(raw.highValue, out)
        if not out.highValue or out.fights <= 32 and not equal(out.highValue, deriveHigh(out)) then return nil end
    elseif out.fights <= 32 then
        out.highValue = deriveHigh(out) -- Every owned settlement is retained; no missing history is invented.
    end
    for k in pairs(raw) do if out[k] == nil then return nil end end
    return out
end
function Ledger.new(storage, scope, evidence)
    if type(storage) ~= "table" or storage.strictRecovery ~= true or type(storage.Read) ~= "function"
        or type(storage.Write) ~= "function" or type(scope) ~= "table" or type(evidence) ~= "table"
        or type(evidence.outcome) ~= "function" or type(evidence.copyOutcome) ~= "function" then
        return nil, "Fight history dependencies unavailable"
    end
    local own, key = {}, "idle-mafia-ember:player-fights:v1:"
    for _, k in ipairs({"account", "place", "release"}) do
        if not text(scope[k]) then return nil, "Invalid fight history scope" end
        own[k], key = scope[k], key .. #scope[k] .. ":" .. scope[k]
    end
    if writers[key] then return nil, "Fight history write in flight" end
    local ok, raw = pcall(storage.Read, storage, key)
    if not ok then return nil, "Fight history read failed" end
    local state = raw ~= nil and copy(raw, own, evidence) or nil
    if raw ~= nil and not state then return nil, "Corrupt fight history" end
    local expected = state and copy(state, own, evidence) or nil
    state = state or {version = 1, account = own.account, place = own.place, release = own.release,
        fights = 0, wins = 0, cash = 0, stamina = 0, lastRequestId = 0, recent = {}, highValue = emptyHigh(0)}
    return setmetatable({storage = storage, scope = own, evidence = evidence, key = key,
        state = state, expected = expected, closed = false}, Methods), nil
end
function Methods:Summary() return copy(self.state, self.scope, self.evidence) end
function Methods:InfoSummary()
    if self.closed or self.fault then return nil end
    local out = {fights = self.state.fights, lastRequestId = self.state.lastRequestId, recent = {}}
    for _, row in ipairs(self.state.recent) do
        out.recent[#out.recent + 1] = {requestId = row.requestId, feature = row.feature,
            receipt = {cashConfirmed = row.receipt.cashConfirmed, won = row.receipt.won}}
    end
    return out
end
function Methods:Close() self.closed = true end
function Methods:Proof(snapshot, highOnly)
    if self.closed or self.fault or type(snapshot) ~= "table" or not text(snapshot.session)
        or not integer(snapshot.revision, 0) or type(snapshot.capturedAt) ~= "number"
        or snapshot.capturedAt ~= snapshot.capturedAt or snapshot.capturedAt < 0 or snapshot.capturedAt > MAX then return nil end
    for _, k in ipairs({"account", "place", "release"}) do if snapshot[k] ~= self.scope[k] then return nil end end
    local result = {recent = {}}
    for _, row in ipairs(self.state.recent) do result.recent[#result.recent + 1] = self.evidence.copyOutcome(row) end
    for _, k in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do result[k] = snapshot[k] end
    if highOnly == true then
        local status = self:HighValueStatus(snapshot)
        result.highValue = {known = status.known, count = status.count, reason = status.reason,
            lastRequestId = self.state.lastRequestId, targets = {}}
        local rows = type(snapshot.hitListProof) == "table" and snapshot.hitListProof.rows
        if status.known and type(rows) == "table" and #rows <= 128 then
            for _, row in ipairs(rows) do
                local key = tostring(row.userId)
                local target = self.state.highValue.targets[key]
                if target then
                    local known, why = self:IsHighValue(snapshot, row.userId)
                    if known ~= true then
                        result.highValue = {known = false, reason = why, lastRequestId = self.state.lastRequestId, targets = {}}
                        break
                    end
                    local saved = {userId = target.userId, history = {}}
                    for _, item in ipairs(target.history) do
                        saved.history[#saved.history + 1] = {requestId=item.requestId,at=item.at,cash=item.cash,won=item.won}
                    end
                    result.highValue.targets[key] = saved
                end
            end
        end
    end
    return result
end
function Methods:History(feature, target, serverNow)
    local result = {}
    if self.closed or self.fault or (feature ~= "combat" and feature ~= "warCombat")
        or not integer(target, 1) or not number(serverNow, 0) then return result end
    for _, row in ipairs(self.state.recent) do
        if row.feature == feature and row.target == target and row.serverNow <= serverNow and serverNow - row.serverNow <= 30 * 86400 then
            result[#result + 1] = {at = row.serverNow, cash = row.receipt.cashConfirmed, won = row.receipt.won}
        end
    end
    return result
end
-- Only retained, owned ordinary settlements are lookup seeds; this is not historical migration.
function Methods:SavedTargets(snapshot)
    local native = type(snapshot) == "table" and snapshot.native
    if self.closed or self.fault or type(native) ~= "table" or native.fullSync ~= true
        or not number(native.serverNow, 0) then return nil end
    for _, key in ipairs({"account", "place", "release"}) do if snapshot[key] ~= self.scope[key] then return nil end end
    local byId, ids = {}, {}
    for _, row in ipairs(self.state.recent) do
        local at = row.initial.targetDaily.serverNow
        if row.feature == "combat" and at <= native.serverNow and native.serverNow - at <= 30 * 86400 then
            local saved = byId[row.target]
            if not saved then saved = {userId = row.target, history = {}}; byId[row.target], ids[#ids + 1] = saved, row.target end
            saved.name, saved.level = row.targetName, row.targetLevel
            saved.history[#saved.history + 1] = {at = at, cash = row.receipt.cashConfirmed, won = row.receipt.won}
        end
    end
    table.sort(ids)
    local result = {}
    for _, id in ipairs(ids) do result[#result + 1] = byId[id] end
    return result
end
function Methods:HighValueStatus(snapshot)
    if self.closed or self.fault or type(snapshot) ~= "table" or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true or not number(snapshot.native.serverNow, 0) then
        return {known=false,reason=self.fault or "High-value history unavailable"}
    end
    for _, key in ipairs({"account", "place", "release"}) do
        if snapshot[key] ~= self.scope[key] then return {known=false,reason="High-value history scope changed"} end
    end
    local memory = self.state.highValue
    if not memory then return {known=false,reason="Older fight history is truncated; high-value history is unknown"} end
    if memory.overflow then return {known=false,retained=memory.count,reason="High-value memory capacity reached; history retained"} end
    return {known=true,count=memory.count,rules=memory.rules}
end
function Methods:IsHighValue(snapshot, id)
    local status = self:HighValueStatus(snapshot)
    if not status.known then return nil, status.reason end
    local target = self.state.highValue.targets[tostring(id)]
    if not target then return false end
    for _, row in ipairs(target.history) do if row.at > snapshot.native.serverNow then return nil, "High-value history is newer than this snapshot" end end
    return true
end
function Methods:HighValueTargets(snapshot)
    local status = self:HighValueStatus(snapshot)
    if not status.known then return nil end
    local ids = {}
    for key in pairs(self.state.highValue.targets) do ids[#ids + 1] = key end
    table.sort(ids, function(a,b) return tonumber(a)<tonumber(b) end)
    local result = {}
    for _, key in ipairs(ids) do
        local target = self.state.highValue.targets[key]
        local row = {userId=target.userId,name=target.name,level=target.level,history={}}
        for _, item in ipairs(target.history) do row.history[#row.history+1]={requestId=item.requestId,at=item.at,cash=item.cash,won=item.won} end
        result[#result+1]=row
    end
    return result
end
function Methods:Record(data, after)
    if self.closed or self.fault then return false, self.fault or "Fight history closed" end
    local row = self.evidence.outcome(data, after)
    if not row then return false, "Exact numbered settled fight required" end
    for _, k in ipairs({"account", "place", "release"}) do
        if data.proposal[k] ~= self.scope[k] then return false, "Fight history scope changed" end
    end
    if writers[self.key] then return false, "Fight history write in flight" end
    writers[self.key] = self
    local attempted = false
    local ok, saved = pcall(function()
        local raw = self.storage:Read(self.key)
        local current = raw ~= nil and copy(raw, self.scope, self.evidence) or nil
        if (raw ~= nil and not current) or not equal(current, self.expected) or self.closed then return false end
        if row.requestId <= self.state.lastRequestId then
            local last = self.state.recent[#self.state.recent]
            return row.requestId == self.state.lastRequestId and equal(last, row)
        end
        for _, previous in ipairs(self.state.recent) do
            if previous.initial.fightId == row.initial.fightId then return false end
        end
        local nextState = self:Summary()
        if nextState.fights >= MAX or nextState.cash > MAX - row.receipt.cashConfirmed
            or nextState.stamina > MAX - row.staminaCost then return false end
        nextState.fights, nextState.wins = nextState.fights + 1, nextState.wins + (row.receipt.won and 1 or 0)
        nextState.cash, nextState.stamina = nextState.cash + row.receipt.cashConfirmed, nextState.stamina + row.staminaCost
        nextState.lastRequestId = row.requestId
        if nextState.highValue then updateHigh(nextState.highValue, row, nextState.recent) end
        if #nextState.recent == 32 then table.remove(nextState.recent, 1) end
        nextState.recent[#nextState.recent + 1] = row
        nextState = copy(nextState, self.scope, self.evidence)
        if not nextState or self.closed then return false end
        attempted = true
        if self.storage:Write(self.key, nextState) == false then return false end
        self.state, self.expected = nextState, copy(nextState, self.scope, self.evidence)
        return not self.closed
    end)
    if writers[self.key] == self then writers[self.key] = nil end
    if not ok or saved ~= true then
        if attempted then self.fault = "Fight history write outcome uncertain; reload required" end
        return false, self.fault or "Fight history save refused"
    end
    return true, nil
end
return Ledger
