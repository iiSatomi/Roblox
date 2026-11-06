-- Saved FightTab read-only GetHitList contract; never proposes an attack.
local HitListQuery = {}
local Methods = {}
Methods.__index = Methods

local function nonempty(value)
    return type(value) == "string" and #value > 0
end

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function finite(value)
    return type(value) == "number" and value == value
        and value > -math.huge and value < math.huge
end

local function dense(rows)
    if type(rows) ~= "table" or #rows > 128 then return false end
    local count = 0
    for key in pairs(rows) do
        if not integer(key, 1) or key > #rows then return false end
        count = count + 1
    end
    return count == #rows
end

function HitListQuery.new(identity, fingerprint, nativeSource, mode)
    assert(type(identity) == "table" and nonempty(identity.account)
        and nonempty(identity.place) and nonempty(identity.release),
        "Missing Combat hit-list identity")
    assert(fingerprint == nil or type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$"), "Invalid hit-list source key")
    assert(nativeSource == nil or type(nativeSource) == "table" and type(nativeSource.Current) == "function",
        "Invalid native hit-list source")
    assert(fingerprint == nil or nonempty(identity.session), "Missing hit-list session")
    assert(mode == nil or mode == "war", "Invalid native roster mode")
    return setmetatable({ account = identity.account, session = identity.session,
        warOnly = mode == "war", proofField = mode == "war" and "warRosterProof" or "hitListProof",
        nativeSource = nativeSource, sourceCurrent = nativeSource and nativeSource.Current,
        place = identity.place, release = identity.release,
        sourceKey = fingerprint and fingerprint:lower() or nil }, Methods)
end

function Methods:Describe(refresh)
    assert(type(refresh) == "boolean", "Hit-list refresh must be boolean")
    assert(not self.warOnly or refresh == false, "War roster has no ordinary refresh")
    return { remote = "GetHitList", method = "InvokeServer",
        arity = 1, args = { self.warOnly and "warStatus" or refresh }, kind = "readOnly",
        source = self.warOnly and "current native WarRosterView refresh" or "saved FightTab refreshHitList" }
end

function Methods:DescribeSearch(term)
    if self.warOnly then return nil, "Ordinary search is not a war roster" end
    if type(term) ~= "string" then return nil, "Invalid target search" end
    local query = term:match("^%s*(.-)%s*$")
    if #query == 0 or #query > 64
        or query:find("[%c]") then
        return nil, "Invalid target search"
    end
    return { remote = "SearchTarget", method = "InvokeServer",
        arity = 1, args = { query }, kind = "readOnly",
        source = "saved FightTab search target call" }, nil
end

local function targetAllowance(value, day)
    if type(value) ~= "table" or value.day ~= day or type(value.canScore) ~= "boolean" then return nil end
    local result = {day = day, canScore = value.canScore}
    for _, key in ipairs({"remaining", "cap", "attacksRemaining", "attacksCap", "pairRemaining"}) do
        if not integer(value[key], 0) or value[key] > 9007199254740991 then return nil end
        result[key] = value[key]
    end
    if result.remaining > result.cap or result.attacksRemaining > result.attacksCap then return nil end
    return result
end

function Methods:Stage(snapshot, reply)
    local input = type(reply) == "table" and reply.list
    if self.warOnly then input = type(reply) == "table" and type(reply.warStatus) == "table" and reply.warStatus.targets end
    if type(snapshot) ~= "table" or snapshot.account ~= self.account
        or snapshot.place ~= self.place or snapshot.release ~= self.release
        or not finite(snapshot.capturedAt)
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true
        or type(reply) ~= "table" or reply.ok ~= true
        or not dense(input)
        or (reply.cooldown ~= nil and type(reply.cooldown) ~= "boolean")
        or (reply.search ~= nil and type(reply.search) ~= "string") then
        return nil, "Current Combat hit list required"
    end
    local rows, seen = {}, {}
    for index, item in ipairs(input) do
        if type(item) ~= "table" or not integer(item.userId, 1)
            or seen[item.userId] or not nonempty(item.name)
            or self.warOnly and (item.userId > 9007199254740991 or #item.name > 64)
            or not integer(item.level, 1)
            or (item.familyId ~= nil and not (integer(item.familyId, 0)
                or type(item.familyId) == "string" and #item.familyId > 0 and #item.familyId <= 120
                    and not item.familyId:find("[%c]")))
            or (item.prestige ~= nil and not integer(item.prestige, 0))
            or (item.respect ~= nil and (not finite(item.respect) or item.respect < 0))
            or (item.online ~= nil and type(item.online) ~= "boolean")
            or (item.stamina ~= nil and not integer(item.stamina, 0))
            or (item.shielded ~= nil and type(item.shielded) ~= "boolean" and not finite(item.shielded)) then
            return nil, "Invalid Combat hit-list row"
        end
        seen[item.userId] = true
        rows[index] = { userId = item.userId, name = item.name,
            level = item.level, online = item.online == true,
            stamina = item.stamina, shielded = item.shielded,
            familyId = item.familyId, prestige = item.prestige, respect = item.respect }
        if self.warOnly then rows[index].warStatus = targetAllowance(item.warStatus, reply.warStatus.day) end
    end
    local result = {}
    for key, value in pairs(snapshot) do result[key] = value end
    result[self.proofField] = { account = self.account,
        capturedAt = snapshot.capturedAt, rows = rows,
        cooldown = reply.cooldown == true, search = reply.search }
    return result, nil
end

function Methods:StageSearch(snapshot, reply, term)
    local call, reason = self:DescribeSearch(term)
    if not call then return nil, reason end
    if type(reply) ~= "table" or reply.search ~= call.args[1] then
        return nil, "Target search reply does not match query"
    end
    return self:Stage(snapshot, reply)
end

local fields = {"session", "account", "place", "release", "revision", "capturedAt"}
local function clone(value)
    if type(value) ~= "table" then return value end
    local out = {}
    for k, child in pairs(value) do out[k] = clone(child) end
    return out
end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not equal(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end
local function header(self, raw)
    if self.closed or self.retired then return nil end
    if self.nativeSource then
        local ok, current = false, false
        if self.nativeSource.Current == self.sourceCurrent then
            ok, current = pcall(self.sourceCurrent, self.nativeSource, "GetHitList")
        end
        if not ok or current ~= true then
            self.retired = true
            self.pending, self.staged, self.observed = nil, nil, nil
            return nil
        end
    end
    if not self.sourceKey or type(raw) ~= "table" or raw.session ~= self.session
        or raw.account ~= self.account or raw.place ~= self.place or raw.release ~= self.release
        or not integer(raw.revision, 0) or not finite(raw.capturedAt) or raw.capturedAt < 0
        or type(raw.native) ~= "table" or raw.native.fullSync ~= true
        or not finite(raw.native.serverNow) or raw.native.serverNow < 0 then return nil end
    local out = {serverNow = raw.native.serverNow}
    for _, k in ipairs(fields) do out[k] = raw[k] end
    return out
end
function Methods:Prepare(snapshot)
    if self.searchRequest then self:CancelSavedSearch(self.searchRequest) end
    self.pending, self.staged = nil, nil
    local bound = header(self, snapshot)
    if not bound then return nil, "Current owned hit-list source unavailable" end
    local request = self:Describe(false)
    self.pending = {request = request, header = bound}
    return request, nil
end
local function warScope(snapshot)
    local native = snapshot.native
    local family, war
    if type(native.family) == "table" then family = native.family.id end
    if type(native.derived) == "table" then war = native.derived.war end
    return {familyId = family, day = math.floor(native.serverNow / 86400),
        warType = type(war), warState = type(war) == "table" and type(war.state) == "string" and war.state or nil,
        warEnemyId = type(war) == "table" and clone(war.enemyId) or nil}
end
local function quoteScope(snapshot)
    local out = {}
    for _, key in ipairs({"level", "maxLevel", "prestige", "respect"}) do out[key] = clone(snapshot.native[key]) end
    return out
end
local function projectWar(raw, snapshot, ordinaryRows)
    if type(raw) ~= "table" or not integer(raw.day, 0) or not finite(raw.serverNow) or raw.serverNow < snapshot.native.serverNow
        or raw.serverNow - snapshot.native.serverNow > 10 or raw.day ~= math.floor(raw.serverNow / 86400) or raw.day ~= math.floor(snapshot.native.serverNow / 86400)
        or not dense(raw.targets) then return nil end
    if raw.summary == nil and #raw.targets == 0 and warScope(snapshot).warState ~= "active" then
        return {active = false, statusServerNow = raw.serverNow}
    end
    if type(raw.summary) == "table" then
        local result = {active = true, statusServerNow = raw.serverNow}
        local scope = warScope(snapshot)
        local function family(value)
            return integer(value, 1) and value <= 9007199254740991
                or type(value) == "string" and #value > 0 and #value <= 120 and not value:find("[%c]")
        end
        -- Native FamilyTab.WarRosterView opens the enemy profile with
        -- summary.enemyId, falling back to targets[1].familyId. Require the
        -- entire bounded roster to agree before using that ID for exclusions.
        local enemy = raw.summary.enemyId
        if enemy == nil and raw.targets[1] then enemy = raw.targets[1].familyId end
        if scope.warState ~= "active" or not family(scope.familyId) or not family(enemy)
            or type(enemy) ~= type(scope.familyId) or enemy == scope.familyId
            or scope.warEnemyId ~= nil and scope.warEnemyId ~= enemy then return result end
        local seen = {}
        for _, row in ipairs(raw.targets) do
            if type(row) ~= "table" or not integer(row.userId, 1) or row.userId > 9007199254740991
                or seen[row.userId] or row.familyId ~= enemy then return result end
            seen[row.userId] = true
        end
        -- A newer roster is a stronger exclusion than conflicting ordinary
        -- metadata. Hold selection until both reads agree about that user.
        for _, row in ipairs(ordinaryRows) do
            if seen[row.userId] and row.familyId ~= enemy then return result end
        end
        result.enemyFamilyId, result.enemyTargets = enemy, {}
        for id in pairs(seen) do result.enemyTargets[tostring(id)] = true end
        local summary = raw.summary
        if integer(summary.ownRemaining, 0) and integer(summary.ownCap, 0)
            and summary.ownCap <= 9007199254740991 and summary.ownRemaining <= summary.ownCap then
            result.ownRemaining, result.ownCap = summary.ownRemaining, summary.ownCap
        end
        if type(summary.canScore) == "boolean" then result.canScore = summary.canScore end
        if type(summary.canFeed) == "boolean" then result.canFeed = summary.canFeed end
        if finite(summary.eligibleAt) and summary.eligibleAt >= 0 then result.eligibleAt = summary.eligibleAt end
        return result
    end
    return nil
end
local function searchCurrent(self)
    if self.closed or self.retired or self.searchRetired or self.warOnly then return false end
    if self.nativeSource then
        local ok, value = false, false
        if self.nativeSource.Current == self.sourceCurrent then ok, value = pcall(self.sourceCurrent, self.nativeSource, "SearchTarget") end
        if not ok or value ~= true then self.searchRetired, self.searched = true, nil; return false end
    end
    return true
end
local function elapsed(now, first, seconds)
    return now.capturedAt >= first.capturedAt + seconds and now.serverNow >= first.serverNow + seconds
end
function Methods:SearchReady(snapshot, target)
    local bound = header(self, snapshot)
    if not bound or not searchCurrent(self) or type(target) ~= "table" or not integer(target.userId, 1)
        or target.userId > 9007199254740991 or not self:DescribeSearch(target.name)
        or self.lastSearch and not elapsed(bound, self.lastSearch, 60) then return false end
    local previous = self.searchAttempts and self.searchAttempts[tostring(target.userId)]
    return previous == nil or elapsed(bound, previous, 1800)
end
function Methods:PickSavedSearch(snapshot, candidates, limit, scope)
    local bound = header(self, snapshot)
    limit, scope = limit or 32, scope or "ordinary"
    if (scope ~= "ordinary" and scope ~= "high") or (limit ~= 32 and limit ~= 128) or not bound or not searchCurrent(self) or not dense(candidates) or #candidates > limit
        or self.lastSearch and not elapsed(bound, self.lastSearch, 60) then return nil end
    local nextTarget, wrapped
    for _, target in ipairs(candidates) do
        local id = type(target) == "table" and target.userId
        if integer(id, 1) and id <= 9007199254740991 and self:DescribeSearch(target.name) then
            local previous = self.searchAttempts and self.searchAttempts[tostring(id)]
            if not previous or elapsed(bound, previous, 1800) then
                if not wrapped or id < wrapped.userId then wrapped = target end
                if id > (self.searchCursors and self.searchCursors[scope] or 0) and (not nextTarget or id < nextTarget.userId) then nextTarget = target end
            end
        end
    end
    local selected = nextTarget or wrapped
    return selected and {userId = selected.userId, name = selected.name, lookupScope = scope} or nil
end
function Methods:OwnsSavedSearch(request)
    return request ~= nil and self.searchRequest == request and searchCurrent(self)
        and not self.closed and not self.retired and not self.searchRetired and self.searchRequest == request
        and (not self.nativeSource or self.nativeSource.Current == self.sourceCurrent)
end
function Methods:CancelSavedSearch(request)
    if request == nil or self.searchRequest ~= request then return false end
    self.searchRequest = nil
    if self.pending and self.pending.expectedUserId then self.pending = nil end
    if self.staged and self.staged.expectedUserId then self.staged = nil end
    self.generation = (self.generation or 0) + 1
    return true
end
function Methods:PrepareSavedSearch(snapshot, target)
    if self.searchRequest then self:CancelSavedSearch(self.searchRequest) end
    self.pending, self.staged = nil, nil
    local scope = type(target) == "table" and (target.lookupScope or "ordinary")
    if scope ~= "ordinary" and scope ~= "high" then return nil, "Invalid saved lookup scope" end
    if not self:SearchReady(snapshot, target) or not self:Read(snapshot) then return nil, "Owned saved lookup is unavailable or cooling down" end
    local bound, request = header(self, snapshot), self:DescribeSearch(target.name)
    if not bound or not searchCurrent(self) then return nil, "Saved lookup source changed" end
    local attempts, count = {}, 0
    for id, first in pairs(self.searchAttempts or {}) do
        if not elapsed(bound, first, 1800) then attempts[id], count = first, count + 1 end
    end
    if count >= 32 then return nil, "Saved lookup window is full" end
    attempts[tostring(target.userId)] = clone(bound)
    self.searchAttempts, self.lastSearch = attempts, clone(bound)
    self.searchCursors = self.searchCursors or {}
    self.searchCursors[scope] = target.userId
    self.searchRequest = request
    self.pending = {request = request, header = bound, generation = self:Generation(),
        expectedUserId = target.userId, term = request.args[1],
        warScope = warScope(snapshot), quoteScope = quoteScope(snapshot)}
    return request, nil
end
function Methods:AcceptSavedSearch(snapshot, request, reply)
    local pending = self.pending
    if not pending or not pending.expectedUserId or not searchCurrent(self)
        or not equal(header(self, snapshot), pending.header) or not equal(warScope(snapshot), pending.warScope)
        or not equal(quoteScope(snapshot), pending.quoteScope) or pending.generation ~= self:Generation()
        or pending.request ~= request or request.remote ~= "SearchTarget" or request.method ~= "InvokeServer"
        or request.arity ~= 1 or type(request.args) ~= "table" or request.args[1] ~= pending.term then
        return nil, "Saved lookup owner changed"
    end
    self.pending = nil
    local staged, why = self:StageSearch(snapshot, reply, pending.term)
    if not staged or reply.pending == true or reply.code == "presence" or reply.code == "busy" or reply.code == "rate_limited" then
        return nil, why or "Saved lookup reply unavailable"
    end
    local proof, exact = staged.hitListProof
    for _, row in ipairs(proof.rows) do
        if row.userId == pending.expectedUserId then exact = row end
    end
    proof.rows = exact and {exact} or {}
    for _, row in ipairs(proof.rows) do
        row.nativeShielded = row.shielded
        if type(row.shielded) == "number" then row.shielded = row.shielded > 0 end
    end
    proof.sourceKey, proof.header = self.sourceKey, clone(pending.header)
    proof.warScope, proof.quoteScope = warScope(snapshot), quoteScope(snapshot)
    self.staged = {value = staged, proof = clone(proof), expectedUserId = pending.expectedUserId, generation = pending.generation}
    return staged, nil
end
function Methods:CommitSavedSearch(staged)
    local pending = self.staged
    self.staged = nil
    if not pending or not pending.expectedUserId or pending.value ~= staged or not searchCurrent(self)
        or pending.generation ~= self:Generation() or not equal(header(self, staged), pending.proof.header)
        or not equal(warScope(staged), pending.proof.warScope) or not equal(quoteScope(staged), pending.proof.quoteScope)
        or not equal(staged.hitListProof, pending.proof) then return false end
    self.searched = pending.proof.rows[1] and pending.proof or nil
    self.searchRequest = nil
    self.generation = (self.generation or 0) + 1
    return true
end
function Methods:Accept(snapshot, request, reply)
    local pending = self.pending
    if not pending or not equal(header(self, snapshot), pending.header) or request ~= pending.request
        or request.remote ~= "GetHitList" or request.method ~= "InvokeServer" or request.arity ~= 1
        or type(request.args) ~= "table" or request.args[1] ~= (self.warOnly and "warStatus" or false) then return nil, "Hit-list read owner changed" end
    local staged, why = self:Stage(snapshot, reply)
    self.pending = nil
    if not staged or reply.pending == true or reply.code == "presence" or reply.code == "rate_limited"
        or reply.search ~= nil then return nil, why or "Current hit-list reply unavailable" end
    local proof = staged[self.proofField]
    for _, row in ipairs(proof.rows) do
        row.nativeShielded = row.shielded
        if type(row.shielded) == "number" then row.shielded = row.shielded > 0 end
    end
    proof.sourceKey, proof.header = self.sourceKey, clone(pending.header)
    proof.war, proof.warScope = projectWar(reply.warStatus, snapshot, proof.rows), warScope(snapshot)
    if proof.war and self.warHighwater
        and proof.war.statusServerNow < self.warHighwater then proof.war = nil end
    proof.quoteScope = quoteScope(snapshot)
    self.staged = {value = staged, proof = clone(proof)}
    return staged, nil
end
function Methods:Commit(staged)
    local pending = self.staged
    self.staged = nil
    if self.closed or not pending or pending.expectedUserId or pending.value ~= staged
        or not equal(header(self, staged), pending.proof.header)
        or not equal(warScope(staged), pending.proof.warScope) or not equal(quoteScope(staged), pending.proof.quoteScope)
        or not equal(staged[self.proofField], pending.proof) then return false end
    self.observed = pending.proof
    if pending.proof.war then self.warHighwater = pending.proof.war.statusServerNow end
    self.generation = (self.generation or 0) + 1
    return true
end
function Methods:Generation()
    if self.closed or self.retired then return nil end
    return self.generation or 0
end
function Methods:Read(snapshot)
    local observed = self.observed
    local bound = observed and header(self, snapshot)
    local first = observed and observed.header
    if not bound or not equal(quoteScope(snapshot), observed.quoteScope) or bound.revision < first.revision or bound.capturedAt < first.capturedAt
        or bound.serverNow < first.serverNow or bound.capturedAt - first.capturedAt > 10
        or bound.serverNow - first.serverNow > 10
        or bound.revision == first.revision and not equal(bound, first)
        or self.warOnly and not equal(warScope(snapshot), observed.warScope) then return nil end
    -- Target metadata is independent of own pool regeneration. Preserve its
    -- actual observation header/time when projecting into a newer own Sync.
    local out = clone(observed)
    out.header, out.capturedAt = bound, bound.capturedAt
    out.readHeader, out.observedAt, out.observedServerNow = clone(first), first.capturedAt, first.serverNow
    if not equal(warScope(snapshot), observed.warScope)
        or out.war and bound.serverNow - out.war.statusServerNow > 10 then out.war = nil end
    if self.searched and searchCurrent(self) then
        -- Search spacing is 60s and metadata expires after 10s: only one lookup can be current.
        local proof, seen = self.searched, false
        local firstSearch, row = proof.header, proof.rows[1]
        for _, current in ipairs(out.rows) do if current.userId == row.userId then seen = true end end
        if #out.rows < 128 and not seen
            and equal(proof.warScope, warScope(snapshot)) and equal(proof.quoteScope, quoteScope(snapshot))
            and bound.revision >= firstSearch.revision and bound.capturedAt >= firstSearch.capturedAt
            and bound.serverNow >= firstSearch.serverNow and bound.capturedAt - firstSearch.capturedAt <= 10
            and bound.serverNow - firstSearch.serverNow <= 10
            and (firstSearch.capturedAt <= out.readHeader.capturedAt and firstSearch.serverNow <= out.readHeader.serverNow
                or firstSearch.capturedAt >= out.readHeader.capturedAt and firstSearch.serverNow >= out.readHeader.serverNow) then
            out.rows[#out.rows + 1] = clone(row)
            if out.war and out.war.active == true and type(out.war.enemyTargets) == "table"
                and out.war.enemyTargets[tostring(row.userId)] and row.familyId ~= out.war.enemyFamilyId then
                out.war.enemyFamilyId = nil -- Preserve the normal reply's stronger roster exclusion.
            end
            if firstSearch.capturedAt < out.readHeader.capturedAt or firstSearch.serverNow < out.readHeader.serverNow then
                out.readHeader, out.observedAt, out.observedServerNow = clone(firstSearch), firstSearch.capturedAt, firstSearch.serverNow
            end
        end
    end
    return out
end
function Methods:NeedsRead(snapshot)
    local proof = self:Read(snapshot)
    return proof == nil or self.observed and self.observed.war ~= nil and proof.war == nil
end
function Methods:Close()
    if self.searchRequest then self:CancelSavedSearch(self.searchRequest) end
    self.closed = true
    self.pending, self.staged, self.observed, self.searched = nil, nil, nil, nil
end
return HitListQuery
