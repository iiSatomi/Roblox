-- One selected own member per request. Read ownership/reservations join Task 24.
local Stationing = {}
local Methods = {}
Methods.__index = Methods
local headers = { "session", "account", "place", "release", "revision", "capturedAt" }
local function number(value, low, high)
    return type(value) == "number" and value == value and value >= low and value <= high
end
local function integer(value, low, high)
    return number(value, low, high) and value % 1 == 0
end
local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs(headers) do if a[field] ~= b[field] then return false end end
    return true
end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function copy(a)
    local result = {}
    for key, value in pairs(a) do result[key] = value end
    return result
end
local function roster(native)
    if type(native) ~= "table" or native.fullSync ~= true
        or not number(native.serverNow, 0, 9007199254740991)
        or type(native.crew) ~= "table" or #native.crew < 2 or #native.crew > 46 then return nil end
    local members, seen, count = {}, {}, 0
    for slot, row in pairs(native.crew) do
        if not integer(slot, 1, #native.crew) or type(row) ~= "table" then return nil end
        count = count + 1
        if slot > 1 then
            if type(row.name) ~= "string" or #row.name == 0 or #row.name > 64
                or not integer(row.rarity, 1, 20) then return nil end
            if type(row.healId) ~= "string" or #row.healId == 0 or #row.healId > 128
                or row.healId:find("%c") then return nil end
            local key = "id:" .. row.healId
            if seen[key] then return nil end
            seen[key] = true
            local injured, recalled, train = row.injuredUntil, row.recalledUntil, row.train
            if injured == nil then injured = 0 end
            if recalled == nil then recalled = 0 end
            if train == nil then train = 0 end
            if not number(injured, 0, 9007199254740991)
                or not number(recalled, 0, 9007199254740991)
                or not integer(train, 0, 1000000)
                or (row.duty ~= nil and row.duty ~= false
                    and (type(row.duty) ~= "string" or #row.duty == 0 or #row.duty > 120))
                or (row.training ~= nil and type(row.training) ~= "table")
                or (row.rolling ~= nil and type(row.rolling) ~= "boolean")
                or (row.recalling ~= nil and type(row.recalling) ~= "boolean")
                or (row.stationed ~= nil and type(row.stationed) ~= "boolean")
                or row.dutyPending == true or row.dutyRemapPending == true then return nil end
            members[slot] = { key = key, name = row.name, rarity = row.rarity,
                duty = row.duty or false, train = train, training = row.training ~= nil,
                rolling = row.rolling == true, recalling = row.recalling == true, stationed = row.stationed == true, injured = injured, recalled = recalled,
                weapon = row.weapon or false, armor = row.armor or false, vehicle = row.vehicle or false }
        end
    end
    if count ~= #native.crew or native.crew[1] == nil then return nil end
    return members, count
end
local function eligible(member, now)
    return member.duty == false and not member.stationed and not member.recalling and not member.training and not member.rolling
        and member.injured <= now and member.recalled <= now
end

function Stationing.new(config, gameData, fingerprint, release)
    local source = type(config) == "table" and config.TERRITORY
    local districts = type(gameData) == "table" and gameData.DISTRICTS_BY_ID
    assert(type(source) == "table" and integer(source.garrisonCap, 1, 1000000)
        and type(districts) == "table" and type(fingerprint) == "string"
        and #fingerprint == 64 and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0, "Missing reviewed stationing terms")
    local cities, districtCaps, count = {}, {}, 0
    local byTier = source.garrisonCapByTier
    if byTier ~= nil then
        assert(type(byTier) == "table", "Invalid tiered garrison capacities")
        local tiers = 0
        for tier, cap in pairs(byTier) do
            tiers = tiers + 1
            assert(tiers <= 20 and integer(tier, 1, 20) and integer(cap, 1, 1000000),
                "Invalid tiered garrison capacity")
        end
    end
    for id, district in pairs(districts) do
        count = count + 1
        assert(count <= 4096 and type(id) == "string" and #id > 0 and #id <= 120
            and type(district) == "table" and type(district.city) == "string"
            and #district.city > 0 and #district.city <= 120, "Invalid district catalog")
        cities[id] = district.city
        assert(district.tier == nil or integer(district.tier, 1, 20), "Invalid district tier")
        districtCaps[id] = byTier and byTier[district.tier or 0] or source.garrisonCap
    end
    return setmetatable({ cap = source.garrisonCap, cities = cities, caps = districtCaps,
        key = fingerprint:lower(), release = release }, Methods)
end
function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table" or snapshot.native.fullSync ~= true then
        return nil, "Current full stationing Sync required"
    end
    local result = copy(snapshot)
    result.stationCatalogProof = { release = self.release, key = self.key,
        cap = self.cap, cities = copy(self.cities), caps = copy(self.caps) }
    return result, nil
end
function Stationing.read(raw, context)
    if not same(raw, context) then return nil, "Stationing snapshot changed" end
    local native, source, catalog = raw.native, raw.territoryDistrict, raw.stationCatalogProof
    local map = raw.territoryMap
    local district = type(source) == "table" and source.district
    local members, count = roster(native)
    if not members or type(native.family) ~= "table" or type(source) ~= "table"
        or not ((type(native.family.id) == "string" and #native.family.id > 0)
            or integer(native.family.id, 1, 9007199254740991))
        or not same(source.header, context)
        or type(district) ~= "table" or district.mine ~= true
        or district.holderId ~= native.family.id or source.familyId ~= native.family.id
        or type(catalog) ~= "table" or catalog.release ~= context.release
        or type(catalog.key) ~= "string" or #catalog.key ~= 64
        or not catalog.key:match("^[%x]+$") or not integer(catalog.cap, 1, 1000000)
        or type(catalog.caps) ~= "table"
        or type(catalog.cities) ~= "table" or type(district.id) ~= "string"
        or type(map) ~= "table" or not same(map.header, context)
        or type(map.cityId) ~= "string" or type(catalog.cities[district.id]) ~= "string"
        or catalog.cities[district.id] ~= map.cityId or type(map.districts) ~= "table"
        or not integer(district.garrisonCount, 0, 1000000)
        or not integer(district.revision, 0, 9007199254740991) then
        return nil, "Current owned district, city and stable Crew proof required"
    end
    if (district.settling ~= nil and type(district.settling) ~= "boolean")
        or (district.shieldUntil ~= nil and not number(district.shieldUntil, 0, 9007199254740991)) then
        return nil, "Invalid district settlement or shield state"
    end
    if district.settling == true or (district.shieldUntil or 0) > native.serverNow then
        return nil, "District is settling or shielded"
    end
    local mapped, rows, seenDistricts = false, 0, {}
    for slot, row in pairs(map.districts) do
        rows = rows + 1
        if rows > 200 or not integer(slot, 1, #map.districts)
            or type(row) ~= "table" or type(row.id) ~= "string" or #row.id == 0
            or seenDistricts[row.id] or type(row.mine) ~= "boolean" then
            return nil, "Invalid stationing map"
        end
        seenDistricts[row.id] = true
        if row.id == district.id and row.mine == true then mapped = true end
    end
    if rows ~= #map.districts or not mapped then
        return nil, "Owned stationing district is outside the current map"
    end
    local cap = district.garrisonCap
    if cap == nil then cap = catalog.caps[district.id] end
    if not integer(cap, 1, 1000000) then return nil, "Invalid current garrison capacity" end
    local view = { members = members, size = count, serverNow = native.serverNow,
        districtId = district.id, districtRevision = district.revision,
        familyId = native.family.id, sourceKey = catalog.key, cap = cap, occupied = district.garrisonCount }
    for _, field in ipairs(headers) do view[field] = raw[field] end
    local ownership = raw.stationReservationProof
    if same(ownership, context) and type(ownership.members) == "table"
        and integer(ownership.attempted, 0, 1000) then
        local reserved, rows = {}, 0
        for key, value in pairs(ownership.members) do
            rows = rows + 1
            if rows > 46 or type(key) ~= "string" or #key > 131 or value ~= true then
                return nil, "Invalid member reservation proof"
            end
            reserved[key] = true
        end
        local pending, count = {}, 0
        if ownership.pendingStation ~= nil then
            if type(ownership.pendingStation) ~= "table" then return nil, "Invalid pending station ownership" end
            for key, value in pairs(ownership.pendingStation) do
                count = count + 1
                if count > 46 or type(key) ~= "string" or #key > 131
                    or not key:match("^id:.+") or value ~= true then return nil, "Invalid pending station identity" end
                pending[key] = true
            end
        end
        if ownership.stationUnknown ~= nil and type(ownership.stationUnknown) ~= "boolean" then return nil, "Invalid station uncertainty" end
        view.pendingStation, view.stationUnknown = pending, ownership.stationUnknown == true
        view.reserved, view.attempted = reserved, ownership.attempted
    end
    return view, nil
end
function Stationing.propose(view, settings)
    if type(settings) ~= "table" or settings.enabled ~= true then return nil, "Stationing disabled" end
    if settings.mode ~= nil and settings.mode ~= "Station" then
        return nil, settings.mode == "Recall" and "Recall requires the durable request owner"
            or "Unknown Crew deployment mode"
    end
    if type(view) ~= "table" or type(view.reserved) ~= "table"
        or not integer(view.attempted, 0, 1000)
        or not integer(settings.memberSlot, 2, 46)
        or not integer(settings.minHome, 0, 45)
        or not integer(settings.maxAttempts, 0, 1000)
        or settings.districtId ~= view.districtId then
        return nil, "Selected district/member and shared reservation ownership required"
    end
    local maximum = settings.maxStationed
    if maximum == nil then maximum = 8 end
    if not integer(maximum, 0, 45) or view.stationUnknown then return nil, "Stationed Crew cap or pending identity requires review" end
    local deployed, count = {}, 0
    for _, row in pairs(view.members) do if row.duty ~= false or row.stationed then deployed[row.key] = true end end
    for key in pairs(view.pendingStation or {}) do deployed[key] = true end
    for _ in pairs(deployed) do count = count + 1 end
    if count >= maximum then return nil, "Maximum own stationed or uncertain Crew reached" end
    if view.attempted >= settings.maxAttempts or view.occupied >= view.cap then
        return nil, "Stationing attempt cap or garrison capacity reached"
    end
    local member, home = view.members[settings.memberSlot], 0
    if not member or not eligible(member, view.serverNow) or view.reserved[member.key] then
        return nil, "Selected member is unavailable or reserved"
    end
    for _, row in pairs(view.members) do
        if eligible(row, view.serverNow) and not view.reserved[row.key] then home = home + 1 end
    end
    if home - 1 < settings.minHome then return nil, "Home defense reserve blocks stationing" end
    local proposal = { session = view.session, account = view.account, place = view.place,
        release = view.release, revision = view.revision, feature = "station",
        actionKey = "station:" .. view.districtId .. ":" .. member.key .. ":" .. view.revision .. ":" .. view.attempted,
        resources = {}, intent = { kind = "territoryStation", districtId = view.districtId,
            memberSlot = settings.memberSlot, memberKey = member.key, familyId = view.familyId,
            districtRevision = view.districtRevision, minHome = settings.minHome,
            maxStationed = maximum, maxAttempts = settings.maxAttempts, attemptedBefore = view.attempted, sourceKey = view.sourceKey } }
    local slots = {}
    for slot = 2, view.size do
        local row = view.members[slot]
        if slot ~= settings.memberSlot and #slots < settings.minHome and eligible(row, view.serverNow)
            and not view.reserved[row.key] then
            slots[#slots + 1] = tostring(slot)
            proposal.intent["homeKey" .. slot] = row.key
        end
    end
    proposal.intent.homeSlots = table.concat(slots, ",")
    return proposal, nil
end
function Stationing.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    local view = Stationing.read(before, before)
    if not view or type(intent) ~= "table" or intent.kind ~= "territoryStation"
        or proposal.feature ~= "station" or proposal.revision ~= before.revision then
        return nil, "Stationing baseline changed"
    end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if proposal[field] ~= before[field] then return nil, "Stationing identity changed" end
    end
    local planned = Stationing.propose(view, { enabled = true, districtId = intent.districtId,
        memberSlot = intent.memberSlot, minHome = intent.minHome, maxStationed = intent.maxStationed, maxAttempts = intent.maxAttempts })
    if not planned or planned.intent.memberKey ~= intent.memberKey
        or intent.familyId ~= view.familyId or intent.districtRevision ~= view.districtRevision
        or intent.sourceKey ~= view.sourceKey or intent.attemptedBefore ~= view.attempted or type(proposal.resources) ~= "table"
        or next(proposal.resources) ~= nil then return nil, "Stationing custody or limits changed" end
    if planned.intent.homeSlots ~= intent.homeSlots then return nil, "Home backup selection changed" end
    for slot = 2, view.size do
        if planned.intent["homeKey" .. slot] ~= intent["homeKey" .. slot] then return nil, "Home backup identity changed" end
    end
    local baseline = copy(view)
    baseline.memberSlot, baseline.memberKey = intent.memberSlot, intent.memberKey
    return baseline, nil
end
local function reconcile(proposal, before, after, reply, baseline, restart)
    local intent = type(proposal) == "table" and proposal.intent
    if type(intent) ~= "table" or type(baseline) ~= "table" or type(reply) ~= "table"
        or type(before) ~= "table" or proposal.feature ~= "station" or intent.kind ~= "territoryStation"
        or intent.memberKey ~= baseline.memberKey or intent.memberSlot ~= baseline.memberSlot
        or intent.districtId ~= baseline.districtId or intent.familyId ~= baseline.familyId
        or intent.sourceKey ~= baseline.sourceKey
        or proposal.revision ~= baseline.revision or before.revision ~= baseline.revision
        or type(after) ~= "table" or type(after.native) ~= "table"
        or type(after.native.family) ~= "table" or after.native.family.id ~= baseline.familyId
        or not number(after.native.serverNow, baseline.serverNow, 9007199254740991)
        or not integer(after.revision, 0, 9007199254740991)
        or not (after.session == baseline.session and after.revision > baseline.revision
            or restart and after.session ~= baseline.session and after.native.serverNow > baseline.serverNow)
        or reply.pending == true or reply.code == "rate_limited" or reply.code == "presence" then return "pending" end
    for _, field in ipairs({"session", "account", "place", "release"}) do
        if proposal[field] ~= baseline[field] or before[field] ~= baseline[field]
            or (field ~= "session" or not restart) and after[field] ~= baseline[field] then return "pending" end
    end
    if after.stationCatalogProof and after.stationCatalogProof.key ~= baseline.sourceKey then return "pending" end
    local current, count = roster(after.native)
    if not current or count ~= baseline.size then return "pending" end
    local matched, unchanged = true, true
    for slot, member in pairs(baseline.members) do
        local row = current[slot]
        if not row then return "pending" end
        if row.key ~= member.key or row.name ~= member.name or row.rarity ~= member.rarity then return "pending" end
        if slot == baseline.memberSlot then
            for key, value in pairs(member) do
                if key ~= "duty" and key ~= "stationed" and not equal(row[key], value) then return "pending" end
            end
            if row.duty ~= member.duty or row.stationed ~= member.stationed then unchanged = false end
            if row.duty ~= baseline.districtId then matched = false end
        end
    end
    if reply.ok == false then return unchanged and "rejected" or "pending" end
    return reply.ok == true and matched and "confirmed" or "pending"
end
function Stationing.evaluate(proposal, before, after, reply, baseline)
    return reconcile(proposal, before, after, reply, baseline, false)
end
function Stationing.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.reply) ~= "table" then return nil end
    local baseline = Stationing.capture(data.proposal, data.before)
    if not baseline or not equal(baseline, data.baseline) then return nil end
    local outcome = reconcile(data.proposal, data.before, after, data.reply, baseline, true)
    return (outcome == "confirmed" or outcome == "rejected") and outcome or nil
end
function Stationing.canDispatch(proposal, latest)
    if type(latest) ~= "table" or type(proposal.intent) ~= "table" then return false end
    local raw, proof = copy(latest), {}
    for _, field in ipairs(headers) do proof[field] = raw[field] end
    local current = Stationing.read(latest, latest)
    if not current then return false end
    proof.pendingStation = copy(current.pendingStation or {})
    proof.pendingStation[proposal.intent.memberKey] = nil -- This dispatch owns its prepared record.
    proof.stationUnknown = current.stationUnknown
    proof.members, proof.attempted = {}, proposal.intent.attemptedBefore
    raw.stationReservationProof = proof -- Shared broker rechecks other holders independently at emission.
    return Stationing.capture(proposal, raw) ~= nil
end
Methods.read = Stationing.read
return Stationing
