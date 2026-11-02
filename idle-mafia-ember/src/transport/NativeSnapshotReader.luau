-- Read-only copy boundary for the saved client's Sync and State changes.
-- The integrator must call ObserveSync only for the actual Sync event.
local NativeSnapshotReader = {}
local Methods = {}
Methods.__index = Methods

local identityKeys = { "session", "account", "place", "release" }

local function copy(value, seen, budget, depth)
    local kind = type(value)
    if kind == "table" then
        if seen[value] or depth > 32 then error("Invalid native state graph") end
        seen[value] = true
        local result = {}
        for key, item in pairs(value) do
            budget.count = budget.count + 1
            if budget.count > 100000
                or (type(key) ~= "string" and type(key) ~= "number") then
                error("Invalid native state size or key")
            end
            result[key] = copy(item, seen, budget, depth + 1)
        end
        seen[value] = nil
        return result
    end
    if kind == "string" or kind == "boolean" or kind == "nil" then
        return value
    end
    if kind == "number" and value == value
        and value > -math.huge and value < math.huge then
        return value
    end
    error("Unsupported native state value")
end

local function copied(raw)
    if type(raw) ~= "table" then return nil end
    local ok, result = pcall(copy, raw, {}, { count = 0 }, 0)
    if ok then return result end
    return nil
end

local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do
        if not equal(value, b[key]) then return false end
    end
    for key in pairs(b) do
        if a[key] == nil then return false end
    end
    return true
end

function NativeSnapshotReader.new(identity, clock, sourceKey)
    assert(type(identity) == "table" and type(clock) == "table"
        and type(clock.Now) == "function", "Missing native reader inputs")
    local bound = {}
    for _, key in ipairs(identityKeys) do
        assert(type(identity[key]) == "string" and #identity[key] > 0,
            "Invalid native reader identity")
        bound[key] = identity[key]
    end
    assert(sourceKey == nil or (type(sourceKey) == "string" and #sourceKey == 64
        and sourceKey:match("^[%x]+$")), "Invalid native reader source key")
    return setmetatable({ identity = bound, clock = clock,
        sourceKey = sourceKey and sourceKey:lower() or nil,
        revision = 0, data = nil, capturedAt = nil,
        fullSync = false, heistBoardProof = nil, familyTakedownProof = nil, familyContributionProof = nil,
        territoryReads = {}, closed = false }, Methods)
end

local function record(self, raw, fullSync)
    if self.closed then return false end
    local data = copied(raw)
    if not data then return false end
    if not fullSync and self.data and equal(data, self.data) then
        return true
    end
    local capturedAt = self.clock:Now()
    if type(capturedAt) ~= "number" or capturedAt ~= capturedAt
        or capturedAt < 0 or capturedAt == math.huge then return false end
    self.revision = self.revision + 1
    self.data = data
    self.capturedAt = capturedAt
    self.fullSync = fullSync
    self.heistBoardProof = nil
    self.familyTakedownProof = nil
    self.familyContributionProof = nil
    self.territoryReads = {}
    return true
end

function Methods:ObserveSync(raw)
    return record(self, raw, true)
end

function Methods:ObserveChanged(raw)
    if not self.data then return false end
    return record(self, raw, false)
end

function Methods:AttachHeistBoard(staged)
    if self.closed or not self.fullSync or not self.data
        or type(staged) ~= "table"
        or type(staged.native) ~= "table"
        or staged.native.fullSync ~= true
        or staged.revision ~= self.revision
        or staged.capturedAt ~= self.capturedAt then return false end
    for _, key in ipairs(identityKeys) do
        if staged[key] ~= self.identity[key] then return false end
    end
    local native = copied(self.data)
    native.fullSync = true
    if not equal(staged.native, native) then return false end
    local proof = copied(staged.heistBoardProof)
    if type(proof) ~= "table"
        or proof.account ~= self.identity.account
        or proof.capturedAt ~= self.capturedAt
        or type(proof.board) ~= "table"
        or proof.board.ok ~= true
        or type(proof.board.rows) ~= "table" then return false end
    if self.sourceKey ~= nil then
        if proof.sourceKey ~= self.sourceKey or type(proof.header) ~= "table" then return false end
        for _, key in ipairs(identityKeys) do if proof.header[key] ~= self.identity[key] then return false end end
        if proof.header.revision ~= self.revision or proof.header.capturedAt ~= self.capturedAt then return false end
    end
    self.heistBoardProof = proof
    return true
end

function Methods:Capture()
    if self.closed then return nil, "Native reader closed" end
    if not self.data then return nil, "No observed full Sync" end
    local native = copied(self.data)
    native.fullSync = self.fullSync
    local view = { revision = self.revision,
        capturedAt = self.capturedAt, fullSync = self.fullSync,
        data = native, native = native }
    for _, key in ipairs(identityKeys) do
        view[key] = self.identity[key]
    end
    if self.heistBoardProof then
        view.heistBoardProof = copied(self.heistBoardProof)
    end
    if self.familyTakedownProof then view.familyTakedownProof = copied(self.familyTakedownProof) end
    if self.familyContributionProof then view.familyContributionProof = copied(self.familyContributionProof) end
    for field, value in pairs(self.territoryReads) do view[field] = copied(value) end
    return view, nil
end

function Methods:AttachFamilyBoss(staged)
    if self.closed or not self.fullSync or not self.data or type(staged) ~= "table"
        or type(staged.native) ~= "table" or staged.native.fullSync ~= true
        or staged.revision ~= self.revision or staged.capturedAt ~= self.capturedAt then return false end
    for _, key in ipairs(identityKeys) do if staged[key] ~= self.identity[key] then return false end end
    local native = copied(self.data)
    native.fullSync = true
    if not equal(staged.native, native) then return false end
    local proof = copied(staged.familyTakedownProof)
    if type(proof) ~= "table" or type(proof.header) ~= "table"
        or self.sourceKey == nil or proof.sourceKey ~= self.sourceKey
        or type(proof.sourceKey) ~= "string" or #proof.sourceKey ~= 64
        or not proof.sourceKey:match("^[%x]+$") or type(proof.state) ~= "table"
        or proof.account ~= self.identity.account or proof.capturedAt ~= self.capturedAt then return false end
    for _, key in ipairs(identityKeys) do if proof.header[key] ~= self.identity[key] then return false end end
    if proof.header.revision ~= self.revision or proof.header.capturedAt ~= self.capturedAt
        or type(native.family) ~= "table" or proof.state.famId ~= native.family.id
        or proof.header.familyId ~= native.family.id or proof.header.serverNow ~= native.serverNow then return false end
    self.familyTakedownProof = proof
    return true
end

function Methods:Close()
    self.closed = true
    self.data = nil
    self.capturedAt = nil
    self.fullSync = false
    self.heistBoardProof = nil
    self.familyTakedownProof = nil
    self.familyContributionProof = nil
    self.territoryReads = {}
end

local territoryFields = {territoryMap = true, territoryDistrict = true, residencyView = true, fortificationView = true}
function Methods:ClearTerritoryRead(field)
    if not territoryFields[field] then return false end
    self.territoryReads[field] = nil
    if field == "territoryMap" then
        self.territoryReads.territoryDistrict, self.territoryReads.fortificationView = nil, nil
    end
    return true
end

function Methods:AttachTerritoryRead(staged)
    if self.closed or not self.fullSync or not self.data or type(staged) ~= "table"
        or type(staged.native) ~= "table" or staged.native.fullSync ~= true
        or staged.revision ~= self.revision or staged.capturedAt ~= self.capturedAt then return false end
    for _, key in ipairs(identityKeys) do if staged[key] ~= self.identity[key] then return false end end
    local native = copied(self.data)
    native.fullSync = true
    if not equal(staged.native, native) then return false end
    local proof = copied(staged.territoryRead)
    if type(proof) ~= "table" or self.sourceKey == nil or proof.sourceKey ~= self.sourceKey
        or not territoryFields[proof.field] or type(proof.value) ~= "table"
        or type(proof.value.header) ~= "table" then return false end
    local bound = proof.value.header
    for _, key in ipairs(identityKeys) do if bound[key] ~= self.identity[key] then return false end end
    if bound.revision ~= self.revision or bound.capturedAt ~= self.capturedAt then return false end
    if (proof.field == "territoryDistrict" or proof.field == "fortificationView")
        and (type(native.family) ~= "table" or proof.value.familyId ~= native.family.id) then return false end
    if proof.field == "territoryMap" then
        local capacity = proof.value.territoryCapacity or native.territoryCapacity
        if type(native.family) ~= "table" or type(capacity) ~= "table" or capacity.familyId ~= native.family.id
            or type(proof.value.cityId) ~= "string" or type(proof.value.districts) ~= "table" then return false end
    end
    if proof.field == "territoryMap" then self:ClearTerritoryRead("territoryMap") end
    self.territoryReads[proof.field] = proof.value
    return true
end

function Methods:AttachFamilyContribution(staged)
    if self.closed or not self.fullSync or not self.data or type(staged) ~= "table"
        or type(staged.native) ~= "table" or staged.native.fullSync ~= true
        or staged.revision ~= self.revision or staged.capturedAt ~= self.capturedAt then return false end
    for _, key in ipairs(identityKeys) do if staged[key] ~= self.identity[key] then return false end end
    local native = copied(self.data)
    native.fullSync = true
    if not equal(staged.native, native) then return false end
    local proof = copied(staged.familyContributionProof)
    if type(proof) ~= "table" or self.sourceKey == nil or proof.sourceKey ~= self.sourceKey
        or type(proof.family) ~= "table" or type(native.family) ~= "table"
        or proof.family.familyId ~= native.family.id or proof.family.actorId ~= tonumber(self.identity.account)
        or proof.revision ~= self.revision or proof.capturedAt ~= self.capturedAt then return false end
    for _, key in ipairs(identityKeys) do if proof[key] ~= self.identity[key] then return false end end
    self.familyContributionProof = proof
    return true
end

return NativeSnapshotReader
