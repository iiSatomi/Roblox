-- Family-only owner reads. A profile may corroborate a committed board row;
-- it cannot supply missing board membership or imply permission to Scout.
local Query, Methods = {}, {}
Methods.__index = Methods
local MAX = 9007199254740991
local fields = {"session", "account", "place", "release", "revision", "capturedAt"}
local function number(v, low) return type(v) == "number" and v == v and v >= low and v <= MAX end
local function integer(v, low) return number(v, low) and v % 1 == 0 end
local function text(v, high) return type(v) == "string" and #v > 0 and #v <= high and not v:find("[%c]") end
local function family(v)
    return text(v, 120) and v ~= "0" and v:match("^[%w_%-]+$") ~= nil or integer(v, 1)
end
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
local function clear(self)
    self.pending, self.staged, self.board, self.cache = nil, nil, nil, {}
    self.generation = self.generation + 1
    self.cursor = 0
end
local function current(self)
    if self.closed or self.retired or not self.enabled then return nil end
    if self.source.Current ~= self.current then self.retired = true; clear(self); return nil end
    for _, remote in ipairs({"HeistAction", "PlayerProfile"}) do
        local ok, current = pcall(self.current, self.source, remote)
        if not ok or current ~= true then self.retired = true; clear(self); return nil end
    end
    return true
end
local function header(self, raw)
    if not current(self) then return nil end
    if type(raw) ~= "table" or not integer(raw.revision, 0) or not number(raw.capturedAt, 0)
        or type(raw.native) ~= "table" or raw.native.fullSync ~= true or not number(raw.native.serverNow, 0)
        or type(raw.native.family) ~= "table" or not family(raw.native.family.id) then return nil end
    local out = {serverNow = raw.native.serverNow, ownFamilyId = raw.native.family.id}
    for _, k in ipairs(fields) do
        if k ~= "revision" and k ~= "capturedAt" and raw[k] ~= self.identity[k] then return nil end
        out[k] = raw[k]
    end
    return out
end
local function validBoard(self, raw, bound)
    local proof = type(raw) == "table" and raw.heistBoardProof
    local board = type(proof) == "table" and proof.board
    if not bound or type(proof) ~= "table" or proof.account ~= bound.account
        or proof.capturedAt ~= bound.capturedAt or proof.query ~= nil or proof.sourceKey ~= self.sourceKey
        or type(proof.header) ~= "table" or type(board) ~= "table" or board.ok ~= true
        or not number(board.serverNow, 0) or math.abs(board.serverNow - bound.serverNow) > 2
        or type(board.rows) ~= "table" or #board.rows > 256 then return nil end
    for _, k in ipairs(fields) do if proof.header[k] ~= bound[k] then return nil end end
    local count, seen = 0, {}
    for i, row in ipairs(board.rows) do
        if type(row) ~= "table" or not (text(row.id, 120) or integer(row.id, 1))
            or seen[type(row.id) .. ":" .. tostring(row.id)] then return nil end
        seen[type(row.id) .. ":" .. tostring(row.id)], count = true, i
    end
    for k in pairs(board.rows) do if not integer(k, 1) or k > count then return nil end end
    return proof
end
local function owned(self, raw)
    local bound = header(self, raw)
    local proof = bound and validBoard(self, raw, bound)
    if not proof or not self.board or not equal(bound, self.board.header)
        or not equal(proof, self.board.proof) then return nil end
    return proof.board, bound
end
local function eligible(self, row, bound)
    return integer(row.ownerId, 1) and text(row.ownerName, 100) and integer(row.ownerLevel, 1)
        and family(row.famId) and tostring(row.famId) ~= tostring(bound.ownFamilyId)
        and row.friend == false and row.famRel ~= "family" and number(row.endsAt, 0)
        and row.endsAt > bound.serverNow and self.relations.familyAllowed(self.policy, row.famId)
end
local function fresh(cached, row, bound)
    return type(cached) == "table" and cached.rowId == row.id and cached.userId == row.ownerId
        and cached.name == row.ownerName and cached.level == row.ownerLevel and cached.familyId == row.famId
        and bound.serverNow >= cached.observedServerNow and bound.serverNow - cached.observedServerNow <= 30
        and bound.capturedAt >= cached.observedAt and bound.capturedAt - cached.observedAt <= 30
end
local function rowKey(row) return type(row.id) .. ":" .. tostring(row.id) end
function Query.new(identity, fingerprint, source, relations)
    assert(type(identity) == "table" and type(source) == "table" and type(source.Current) == "function"
        and type(relations) == "table" and type(relations.relations) == "function"
        and type(relations.familyAllowed) == "function" and type(fingerprint) == "string"
        and #fingerprint == 64 and fingerprint:match("^[%x]+$"), "Missing Heist owner Family dependencies")
    local own = {}
    for _, k in ipairs({"session", "account", "place", "release"}) do
        assert(text(identity[k], 200), "Invalid Heist owner scope"); own[k] = identity[k]
    end
    return setmetatable({identity = own, sourceKey = fingerprint:lower(), source = source,
        current = source.Current, relations = relations, cache = {}, generation = 0}, Methods)
end
function Methods:Configure(settings)
    local policy = type(settings) == "table" and self.relations.relations(settings) or nil
    local enabled = not self.closed and not self.retired and policy ~= nil and settings.enabled == true
        and (next(policy.allies) ~= nil or policy.mode ~= "Off")
    local key = enabled and {relationAllies = settings.relationAllies or "",
        relationEnemies = settings.relationEnemies or "", enemyMode = settings.enemyMode or "Off"} or nil
    if self.enabled ~= enabled or not equal(self.policyKey, key) then clear(self) end
    self.enabled, self.policy, self.policyKey = enabled, policy, key
    return enabled
end
-- Called only after NativeSnapshotReader accepts the source-owned board reply.
function Methods:ObserveBoard(raw)
    local bound = header(self, raw)
    local proof = bound and validBoard(self, raw, bound)
    self.generation = self.generation + 1
    self.pending, self.staged = nil, nil
    if not proof then self.board, self.cache = nil, {}; return false end
    if self.board and self.board.header.ownFamilyId ~= bound.ownFamilyId then self.cache = {} end
    local cache = {}
    for _, row in ipairs(proof.board.rows) do
        local old = self.cache[rowKey(row)]
        if eligible(self, row, bound) and fresh(old, row, bound) then cache[rowKey(row)] = old end
    end
    self.cache, self.board = cache, {header = clone(bound), proof = clone(proof)}
    return true
end
function Methods:Read(raw)
    local board, bound = owned(self, raw)
    if not board then return nil end
    local proof = {header = {}, sourceKey = self.sourceKey, ownFamilyId = bound.ownFamilyId,
        policy = clone(self.policyKey), rows = {}}
    for _, k in ipairs(fields) do proof.header[k] = bound[k] end
    for _, row in ipairs(board.rows) do
        local cached = self.cache[rowKey(row)]
        if eligible(self, row, bound) and fresh(cached, row, bound) then proof.rows[#proof.rows + 1] = clone(cached) end
    end
    return proof
end
local function candidate(self, raw)
    local board, bound = owned(self, raw)
    if not board then return nil end
    local choices = {}
    for _, row in ipairs(board.rows) do
        if eligible(self, row, bound) and not fresh(self.cache[rowKey(row)], row, bound) then choices[#choices + 1] = row end
    end
    table.sort(choices, function(a, b)
        local ae = self.policy.mode == "Prefer enemies" and self.policy.enemies[tostring(a.famId)] == true
        local be = self.policy.mode == "Prefer enemies" and self.policy.enemies[tostring(b.famId)] == true
        if ae ~= be then return ae end
        return rowKey(a) < rowKey(b)
    end)
    if #choices == 0 then return nil end
    local index = (self.cursor or 0) % #choices + 1
    return choices[index], bound, index
end
function Methods:NeedsRead(raw) return candidate(self, raw) ~= nil end
function Methods:Prepare(raw)
    self.pending, self.staged = nil, nil
    local row, bound, index = candidate(self, raw)
    if not row then return nil, "No current unprofiled Heist owner" end
    self.cursor = index
    local request = {remote = "PlayerProfile", method = "InvokeServer", arity = 1, args = {row.ownerId}, kind = "readOnly"}
    self.pending = {request = request, row = clone(row), header = bound, generation = self.generation}
    return request, nil
end
function Methods:Accept(raw, request, reply)
    local pending = self.pending
    local board, bound = owned(self, raw)
    if not pending or request ~= pending.request or not board or not equal(bound, pending.header)
        or pending.generation ~= self.generation or request.remote ~= "PlayerProfile"
        or request.method ~= "InvokeServer" or request.arity ~= 1 or type(request.args) ~= "table"
        or request.args[1] ~= pending.row.ownerId then return nil, "Heist owner read changed" end
    self.pending = nil
    local profile = type(reply) == "table" and reply.profile
    if type(reply) ~= "table" or reply.ok ~= true or reply.pending == true or reply.code == "presence"
        or reply.code == "rate_limited" or type(profile) ~= "table" or profile.userId ~= pending.row.ownerId
        or profile.name ~= pending.row.ownerName or profile.level ~= pending.row.ownerLevel
        or not family(profile.familyId) or profile.familyId ~= pending.row.famId
        or profile.serverNow ~= nil and (not number(profile.serverNow, 0)
            or profile.serverNow + 1 < bound.serverNow or profile.serverNow - bound.serverNow > 30) then
        return nil, "Native Heist owner identity or Family changed"
    end
    local row = {rowId = pending.row.id, userId = profile.userId, name = profile.name, level = profile.level,
        familyId = profile.familyId, observedAt = bound.capturedAt, observedServerNow = bound.serverNow}
    local staged = {}; for k, v in pairs(raw) do staged[k] = v end
    staged.sabotageOwnerRead = clone(row)
    self.staged = {value = staged, row = row, header = bound, generation = self.generation}
    return staged, nil
end
function Methods:Commit(staged)
    local pending = self.staged
    self.staged = nil
    local board, bound = owned(self, staged)
    if not pending or staged ~= pending.value or not board or not equal(bound, pending.header)
        or pending.generation ~= self.generation or not equal(staged.sabotageOwnerRead, pending.row) then return false end
    self.cache[type(pending.row.rowId) .. ":" .. tostring(pending.row.rowId)] = clone(pending.row)
    return true
end
-- The adapter checks this immediately before emission, including source changes
-- that happened without another planner tick.
function Methods:CanDispatch(proposal)
    local intent = type(proposal) == "table" and proposal.intent
    if not current(self) or not self.board or type(intent) ~= "table" or intent.ownerProfileRequired ~= true
        or intent.ownerSourceKey ~= self.sourceKey or intent.ownFamilyId ~= self.board.header.ownFamilyId
        or intent.ownerPolicyAllies ~= self.policyKey.relationAllies
        or intent.ownerPolicyEnemies ~= self.policyKey.relationEnemies
        or intent.ownerPolicyMode ~= self.policyKey.enemyMode then return false end
    for _, field in ipairs({"session", "account", "place", "release", "revision"}) do
        if proposal[field] ~= self.board.header[field] then return false end
    end
    for _, row in ipairs(self.board.proof.board.rows) do
        if row.id == intent.rowId then
            local cached = self.cache[rowKey(row)]
            return eligible(self, row, self.board.header) and fresh(cached, row, self.board.header)
                and cached.userId == intent.ownerId and cached.familyId == intent.ownerFamilyId
                and cached.name == intent.ownerProfileName and cached.level == intent.ownerProfileLevel
                and cached.observedAt == intent.ownerProfileAt and cached.observedServerNow == intent.ownerProfileServerNow
        end
    end
    return false
end
function Methods:Close() self.closed = true; clear(self) end
return Query
