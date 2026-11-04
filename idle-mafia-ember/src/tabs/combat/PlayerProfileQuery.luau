-- Profile facts are target-bound reads. Roblox friendship results may be cached.
-- Hidden stats stay hidden; lookup failures remain unknown. No Scout/Attack call.
local Query, Methods = {}, {}
Methods.__index = Methods
local MAX = 9007199254740991
local fields = {"session", "account", "place", "release", "revision", "capturedAt"}
local function number(v, low) return type(v) == "number" and v == v and v >= low and v <= MAX end
local function integer(v, low) return number(v, low) and v % 1 == 0 end
local function text(v, high) return type(v) == "string" and #v > 0 and #v <= high and not v:find("[%c]") end
local function family(v) return v == nil or integer(v, 0) or text(v, 120) end
local function clone(v)
    if type(v) ~= "table" then return v end
    local out = {}; for k, child in pairs(v) do out[k] = clone(child) end; return out
end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not equal(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end
local function retire(self)
    self.retired = true
    self.pending, self.staged, self.cache, self.scoutCache = nil, nil, {}, {}
end
local function header(self, raw)
    if self.closed or self.retired then return nil end
    if self.source.Current ~= self.current or self.source.Friendship ~= self.friendship then retire(self); return nil end
    local ok, current = pcall(self.current, self.source, "PlayerProfile")
    if not ok or current ~= true then retire(self); return nil end
    if type(raw) ~= "table" or not integer(raw.revision, 0) or not number(raw.capturedAt, 0)
        or type(raw.native) ~= "table" or raw.native.fullSync ~= true or not number(raw.native.serverNow, 0) then return nil end
    local out = {serverNow = raw.native.serverNow}
    for _, k in ipairs(fields) do
        if k ~= "revision" and k ~= "capturedAt" and raw[k] ~= self.identity[k] then return nil end
        out[k] = raw[k]
    end
    return out
end
local function fresh(row, target, bound)
    return type(row) == "table" and row.userId == target.userId and row.level == target.level
        and row.name == target.name and row.familyId == target.familyId
        and bound.serverNow >= row.observedServerNow and bound.serverNow - row.observedServerNow <= 30
        and bound.capturedAt >= row.observedAt and bound.capturedAt - row.observedAt <= 30
end
local function profile(raw, target, bound)
    -- Native public replies omit hidden-stat and Scout-only fields. Require all
    -- public numbers before accepting that shape; explicit hidden stays hidden.
    local hidden = type(raw) == "table" and raw.statsHidden
    if type(raw) == "table" and raw.statsHidden == nil and raw.scoutCost == nil
        and number(raw.atk, 1) and number(raw.def, 1) and number(raw.crew, 0) then hidden = false end
    if type(raw) ~= "table" or raw.userId ~= target.userId or raw.level ~= target.level
        or raw.name ~= target.name or not integer(raw.maxLevel, raw.level) or not family(raw.familyId)
        or raw.familyId ~= target.familyId or type(hidden) ~= "boolean"
        or (hidden or raw.scoutCost ~= nil) and (not integer(raw.scoutCost, 1) or raw.scoutCost > 5) then return nil end
    local row = {userId = raw.userId, name = raw.name, level = raw.level, maxLevel = raw.maxLevel,
        familyId = raw.familyId, scoutCost = raw.scoutCost, statsHidden = hidden,
        observedServerNow = bound.serverNow, observedAt = bound.capturedAt, friendshipStatus = "unknown", shieldStatus = "unknown"}
    if raw.shieldLeft ~= nil then
        if not number(raw.shieldLeft, 0) then return nil end
        row.shieldStatus = raw.shieldLeft > 0 and "shielded" or "clear"
        if raw.shieldLeft > 0 then
            local at = bound.serverNow + 30 -- Missing reply clock cannot expire a shield within this cache's lifetime.
            if raw.serverNow ~= nil then
                if not number(raw.serverNow, 0) or raw.serverNow + 1 < bound.serverNow
                    or raw.serverNow - bound.serverNow > 30 then return nil end
                at = math.max(bound.serverNow, raw.serverNow % 1 == 0 and raw.serverNow + 1 or raw.serverNow)
            end
            row.shieldUntil = at + raw.shieldLeft
            if not number(row.shieldUntil, 0) then return nil end
        end
    end
    if hidden == false then
        if not number(raw.atk, 1) or not number(raw.def, 1) or not number(raw.crew, 0) then return nil end
        row.attack, row.defense, row.crew = raw.atk, raw.def, raw.crew
    end
    return row
end
function Query.new(identity, fingerprint, targets, source, scoutEvidence)
    assert(type(identity) == "table" and type(targets) == "table" and type(targets.Read) == "function"
        and type(targets.Generation) == "function" and type(source) == "table" and type(source.Current) == "function"
        and type(fingerprint) == "string" and #fingerprint == 64 and fingerprint:match("^[%x]+$"),
        "Missing owned profile source dependencies")
    local own = {}
    for _, k in ipairs({"session", "account", "place", "release"}) do
        assert(text(identity[k], 200), "Invalid player profile scope"); own[k] = identity[k]
    end
    return setmetatable({identity = own, sourceKey = fingerprint:lower(), targets = targets, source = source,
        current = source.Current, friendship = source.Friendship, cache = {}, scoutCache = {}, sequence = 0,
        scoutEvidence = scoutEvidence, scoutOutcome = type(scoutEvidence) == "table" and scoutEvidence.outcome or nil}, Methods)
end
function Methods:Read(snapshot)
    local bound = header(self, snapshot)
    local list = bound and self.targets:Read(snapshot)
    if not list or list.sourceKey ~= self.sourceKey then return nil end
    local out = {}
    for _, target in ipairs(list.rows) do
        local cached = self.cache[tostring(target.userId)]
        if fresh(cached, target, bound) then
            local row = clone(cached)
            local scout = self.scoutCache[tostring(target.userId)]
            if scout and scout.target == target.userId and scout.name == target.name and scout.level == target.level
                and scout.familyId == target.familyId and scout.sourceKey == self.sourceKey
                and bound.serverNow >= scout.at and bound.serverNow - scout.at <= 1800
                and bound.capturedAt >= scout.cachedAt and bound.capturedAt - scout.cachedAt <= 1800 then
                row.scout = {at = scout.at, defense = scout.defense, level = scout.level, kind = "scout"}
            end
            out[tostring(target.userId)] = row
        end
    end
    return out
end
local function eligible(self, list, row, snapshot)
    if not self.targets.warOnly then return row.shielded == false end
    local war, allowance = list.war, row.warStatus
    return type(war) == "table" and war.active == true and war.canScore == true
        and war.enemyFamilyId ~= nil and row.familyId == war.enemyFamilyId and row.shielded ~= true
        and (war.eligibleAt == nil or war.eligibleAt <= snapshot.native.serverNow)
        and type(allowance) == "table" and allowance.day == math.floor(snapshot.native.serverNow / 86400)
        and allowance.canScore == true and integer(allowance.remaining, 1)
        and integer(allowance.attacksRemaining, 1) and integer(allowance.pairRemaining, 1)
end
local function currentTarget(self, snapshot, expected)
    local list = self.targets:Read(snapshot)
    if not list or list.sourceKey ~= self.sourceKey then return false end
    for _, row in ipairs(list.rows) do
        if row.userId == expected.userId then return equal(row, expected) and eligible(self, list, row, snapshot) end
    end
    return false
end
local function candidate(self, snapshot, maxPublicAge)
    local known = self:Read(snapshot)
    local list = known and self.targets:Read(snapshot)
    if not list then return nil end
    local age = number(maxPublicAge, 1) and maxPublicAge <= 1800 and math.min(30, maxPublicAge) or 30
    for offset = 1, #list.rows do
        local index = ((self.cursor or 0) + offset - 1) % #list.rows + 1
        local row = list.rows[index]
        local cached = known[tostring(row.userId)]
        local needs = not cached or cached.statsHidden == false
            and (snapshot.native.serverNow - cached.observedServerNow > age or snapshot.capturedAt - cached.observedAt > age)
        if needs and eligible(self, list, row, snapshot) then return clone(row), index end
    end
    return nil
end
function Methods:NeedsRead(snapshot, maxPublicAge) return candidate(self, snapshot, maxPublicAge) ~= nil end
function Methods:Prepare(snapshot, maxPublicAge)
    self.sequence = self.sequence + 1
    self.pending, self.staged = nil, nil
    local target, index = candidate(self, snapshot, maxPublicAge)
    local bound = header(self, snapshot)
    if not target or not bound then return nil, "No current unprofiled target" end
    self.cursor = index -- A refused/unavailable target cannot monopolize later reads.
    local request = {remote = "PlayerProfile", method = "InvokeServer", arity = 1,
        args = {target.userId}, kind = "readOnly"}
    self.pending = {request = request, target = target, header = bound,
        generation = self.targets:Generation(), sequence = self.sequence}
    return request, nil
end
function Methods:Accept(snapshot, request, reply)
    local pending = self.pending
    if not pending or request ~= pending.request or not equal(header(self, snapshot), pending.header)
        or self.targets:Generation() ~= pending.generation or request.remote ~= "PlayerProfile"
        or request.method ~= "InvokeServer" or request.arity ~= 1 or type(request.args) ~= "table"
        or request.args[1] ~= pending.target.userId or not currentTarget(self, snapshot, pending.target) then return nil, "Profile read owner changed" end
    self.pending = nil
    if type(reply) ~= "table" or reply.ok ~= true or reply.pending == true or reply.code == "presence"
        or reply.code == "rate_limited" then return nil, "Native player profile unavailable" end
    local row = profile(reply.profile, pending.target, pending.header)
    if not row then return nil, "Native player profile identity or quote changed" end
    if type(self.friendship) == "function" then
        local ok, value = pcall(self.friendship, self.source, row.userId)
        if ok and type(value) == "boolean" then
            row.friend, row.friendshipStatus = value, "reported"
            row.friendshipObservedAt = pending.header.serverNow
        end
    end
    if self.sequence ~= pending.sequence or not equal(header(self, snapshot), pending.header)
        or self.targets:Generation() ~= pending.generation or not currentTarget(self, snapshot, pending.target) then return nil, "Profile source changed during lookup" end
    local staged = {}; for k, v in pairs(snapshot) do staged[k] = v end
    staged.playerProfileRead = clone(row)
    self.staged = {value = staged, row = row, target = pending.target, header = pending.header, generation = pending.generation}
    return staged, nil
end
function Methods:Commit(staged)
    local pending = self.staged
    self.staged = nil
    if not pending or staged ~= pending.value or not equal(header(self, staged), pending.header)
        or self.targets:Generation() ~= pending.generation or not equal(staged.playerProfileRead, pending.row)
        or not currentTarget(self, staged, pending.target) then return false end
    local list = self.targets:Read(staged)
    if not list then return false end
    local nextCache = {}
    for _, target in ipairs(list.rows) do
        local key = tostring(target.userId)
        if self.cache[key] then nextCache[key] = self.cache[key] end
    end
    nextCache[tostring(pending.row.userId)] = pending.row
    self.cache = nextCache
    return true
end
-- The result is already durable in the numbered checkpoint. Cache admission
-- occurs before cleanup; cache loss never refunds a sent Scout or replays it.
function Methods:RecordScout(data, after)
    local bound = header(self, after)
    if not bound or type(self.scoutOutcome) ~= "function" or self.scoutEvidence.outcome ~= self.scoutOutcome then
        return false, "Owned Scout result source unavailable"
    end
    local row = self.scoutOutcome(data, after)
    if type(row) ~= "table" or row.sourceKey ~= self.sourceKey then return false, "Exact numbered Scout result required" end
    local list = self.targets:Read(after)
    local nextCache = {}
    if list then
        for _, target in ipairs(list.rows) do
            local key = tostring(target.userId)
            if self.scoutCache[key] then nextCache[key] = self.scoutCache[key] end
            if row.target == target.userId and row.name == target.name and row.level == target.level
                and row.familyId == target.familyId and row.at <= bound.serverNow and bound.serverNow - row.at <= 1800 then
                row.cachedAt = bound.capturedAt
                nextCache[key] = clone(row)
            end
        end
    end
    self.scoutCache = nextCache
    return true, nil
end
function Methods:Close()
    self.closed = true
    self.pending, self.staged, self.cache, self.scoutCache = nil, nil, {}, {}
end
return Query
