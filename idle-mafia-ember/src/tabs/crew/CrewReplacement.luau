-- One funded ordinary dismiss/hire, never native autoroll. Dismiss has no server identity guard.
local CrewReplacement = {}
local MAX = 9007199254740991
local headers = { "session", "account", "place", "release", "revision", "capturedAt" }
local function number(v, low, high) return type(v) == "number" and v == v and v >= low and v <= high end
local function integer(v, low, high) return number(v, low, high) and v % 1 == 0 end
local function text(v, limit) return type(v) == "string" and #v > 0 and #v <= limit end
local function copy(value)
    local seen, nodes, bytes = {}, 0, 0
    local function clone(v, depth)
        nodes = nodes + 1
        if nodes > 16000 or depth > 14 then error("Replacement record exceeds bounds") end
        if type(v) == "table" then
            if seen[v] then error("Cyclic replacement record") end
            seen[v] = true
            local result, count = {}, 0
            for key, child in pairs(v) do
                count = count + 1
                if count > 128 or not (text(key, 128) or integer(key, 1, 128)) then error("Invalid record key") end
                result[key] = clone(child, depth + 1)
            end
            seen[v] = nil
            return result
        end
        if type(v) == "string" then
            bytes = bytes + #v
            if #v > 32768 or bytes > 262144 then error("Oversized replacement record") end
            return v
        end
        if type(v) == "boolean" or number(v, -MAX, MAX) then return v end
        error("Invalid replacement record scalar")
    end
    local ok, result = pcall(clone, value, 0)
    return ok and result or nil
end
local function same(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not same(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function signature(value)
    local safe = copy(value)
    if not safe then return nil end
    local function encode(v)
        if type(v) ~= "table" then
            local s = type(v) == "number" and string.format("%.17g", v) or tostring(v)
            return type(v) .. #s .. ":" .. s
        end
        local keys, parts = {}, {}
        for key in pairs(v) do keys[#keys + 1] = key end
        table.sort(keys, function(a, b) return type(a) .. tostring(a) < type(b) .. tostring(b) end)
        for _, key in ipairs(keys) do parts[#parts + 1] = encode(key) .. encode(v[key]) end
        return "{" .. table.concat(parts) .. "}"
    end
    local encoded = encode(safe)
    return #encoded <= 32768 and encoded or nil
end
local function identity(a, b, restart)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not text(a[field], 200) or not text(b[field], 200)
            or (not (restart and field == "session") and a[field] ~= b[field]) then return false end
    end
    return true
end
local function matched(proof, raw)
    if type(proof) ~= "table" then return false end
    for _, field in ipairs(headers) do if proof[field] ~= raw[field] then return false end end
    return true
end
local function settingsFrom(intent)
    return { enabled = true, allowDismiss = intent.allowDismiss, slot = intent.slot, tier = intent.tier,
        targetRarity = intent.targetRarity, maxDismissRarity = intent.maxDismissRarity,
        cashReserve = intent.cashReserve, minHome = intent.minHome, maxCost = intent.maxCost,
        maxSpend = intent.maxSpend, maxAttempts = intent.maxAttempts }
end
local function ready(row, now)
    return row.rarity ~= nil and row.duty == nil and row.training == nil and row.rolling ~= true
        and row.stationed ~= true and row.dutyPending ~= true and row.dutyRemapPending ~= true
        and (row.injuredUntil or 0) <= now and (row.recalledUntil or 0) <= now
end
local function selected(row, now)
    if not ready(row, now) or (row.train or 0) ~= 0 or (row.trainLevel or 0) ~= 0
        or row.weapon ~= nil or row.armor ~= nil or row.vehicle ~= nil or row.border ~= nil then return false end
    for key, value in pairs(row) do
        if not text(key, 64) or type(value) == "table" or type(value) == "string" and #value > 128 then return false end
    end
    return true
end
local function rowValid(row)
    if type(row) ~= "table" or not signature(row) then return false end
    if row.rarity == nil then return next(row) == nil end
    if not text(row.name, 64) or not integer(row.rarity, 1, 8)
        or not integer(row.atk, 0, MAX) or not integer(row.def, 0, MAX)
        or row.healId ~= nil and not text(row.healId, 128) then return false end
    for _, key in ipairs({ "injuredUntil", "recalledUntil", "train", "trainLevel" }) do
        if row[key] ~= nil and not number(row[key], 0, MAX) then return false end
    end
    for _, key in ipairs({ "rolling", "stationed", "dutyPending", "dutyRemapPending" }) do
        if row[key] ~= nil and type(row[key]) ~= "boolean" then return false end
    end
    return true
end
function CrewReplacement.new(config, fingerprint, release)
    if type(config) ~= "table" or type(config.CREW) ~= "table" or type(config.CREW.hireTiers) ~= "table"
        or not text(release, 200) or type(fingerprint) ~= "string" or #fingerprint ~= 64
        or not fingerprint:match("^[%x]+$") then return nil, "Reviewed Crew hire source required" end
    local tiers, count = {}, 0
    for index, row in pairs(config.CREW.hireTiers) do
        count = count + 1
        if not integer(index, 1, 8) or type(row) ~= "table" or not text(row.id, 64)
            or not row.id:match("^[%w_]+$") or tiers[row.id] or not integer(row.cost, 1, MAX) then return nil, "Invalid hire tier" end
        local saved = { cost = row.cost }
        for _, key in ipairs({ "odds", "oddsLucky" }) do
            if type(row[key]) ~= "table" or #row[key] ~= 8 then return nil, "Eight native hire odds required" end
            local odds, total, size = {}, 0, 0
            for rarity, chance in pairs(row[key]) do
                if not integer(rarity, 1, 8) or not number(chance, 0, 100) then return nil, "Invalid hire odds" end
                size, total, odds[rarity] = size + 1, total + chance, chance
            end
            if size ~= 8 or total < 99.9 or total > 100.1 then return nil, "Invalid hire odds total" end
            saved[key] = odds
        end
        tiers[row.id] = saved
    end
    if count < 1 or count ~= #config.CREW.hireTiers then return nil, "Dense hire tiers required" end
    local key = fingerprint:lower()
    local result = { key = key, release = release, Copy = copy, Same = same }
    function result:Enrich(raw)
        if type(raw) ~= "table" or raw.release ~= release then return nil, "Matching Crew release required" end
        local enriched = {}
        for field, value in pairs(raw) do enriched[field] = value end
        enriched.crewReplacementSourceKey = key
        return enriched, nil
    end
    result.read = function(raw, context)
        if not identity(raw, context) or not matched(context, raw) or raw.release ~= release
            or raw.crewReplacementSourceKey ~= key or not integer(raw.revision, 0, MAX)
            or not number(raw.capturedAt, 0, MAX) or type(raw.native) ~= "table" then
            return nil, "Current source-bound Crew snapshot required"
        end
        local native = raw.native
        if native.fullSync ~= true or not number(native.serverNow, 0, MAX) or not number(native.cash, 0, MAX)
            or not text(native.cityId, 128) or type(native.crew) ~= "table" or #native.crew < 2 or #native.crew > 46
            or native.autoRolls ~= nil and (type(native.autoRolls) ~= "table" or next(native.autoRolls) ~= nil)
            or type(native.derived) ~= "table" or native.derived.luckyHire ~= nil and type(native.derived.luckyHire) ~= "boolean" then
            return nil, "Complete Crew custody with no native autoroll required"
        end
        local roster, size, empty, home, ids = {}, 0, {}, 0, {}
        for slot, row in pairs(native.crew) do
            size = size + 1
            if not integer(slot, 1, #native.crew) or type(row) ~= "table" then return nil, "Dense Crew roster required" end
            if slot > 1 then
                if not rowValid(row) or row.rolling == true then return nil, "Valid nonrolling Crew required" end
                if row.healId then
                    if ids[row.healId] then return nil, "Duplicate Crew identity" end
                    ids[row.healId] = true
                end
                if row.rarity == nil then empty[#empty + 1] = slot
                elseif ready(row, native.serverNow) then home = home + 1 end
            end
            roster[slot] = copy(row)
            if not roster[slot] then return nil, "Crew member exceeds custody bounds" end
        end
        if size ~= #native.crew then return nil, "Sparse Crew roster" end
        local rosterSignature = signature(roster)
        if not rosterSignature then return nil, "Crew signature exceeds bounds" end
        local proof = raw.economyProof
        if type(proof) ~= "table" or proof.account ~= raw.account or proof.capturedAt ~= raw.capturedAt
            or proof.city ~= native.cityId or not integer(proof.revision, 0, MAX)
            or type(proof.familyId) ~= "string" or #proof.familyId > 200
            or type(proof.rulerId) ~= "string" or #proof.rulerId > 200
            or not integer(proof.hirePct, -25, 25) then return nil, "Current native hire decree proof required" end
        local pct = #proof.familyId > 0 and proof.familyId == proof.rulerId and math.min(proof.hirePct, 0) or proof.hirePct
        local view = { sourceKey = key, roster = roster, size = size, empty = empty, home = home,
            rosterSignature = rosterSignature, serverNow = native.serverNow, cash = native.cash,
            cityId = native.cityId, familyId = proof.familyId, rulerId = proof.rulerId,
            hirePct = pct, decreeRevision = proof.revision, lucky = native.derived.luckyHire == true }
        for _, field in ipairs(headers) do view[field] = raw[field] end
        local usage, owner = raw.crewReplacementUsageProof, raw.crewReplacementOwnerProof
        if matched(usage, raw) and integer(usage.attempted, 0, 1000) and integer(usage.spent, 0, MAX)
            and usage.controllersClear == true then view.attempted, view.spent = usage.attempted, usage.spent end
        if matched(owner, raw) and text(owner.ownerId, 120) and integer(owner.slot, 2, size) then
            view.ownerId, view.ownerSlot = owner.ownerId, owner.slot
        end
        -- Only fields necessary for current/restarted custody, quote and proof validation are retained.
        view.raw = { native = { fullSync = true, serverNow = native.serverNow, cash = native.cash,
            cityId = native.cityId, crew = roster, autoRolls = {}, derived = { luckyHire = view.lucky } },
            economyProof = copy(proof), crewReplacementUsageProof = copy(usage),
            crewReplacementOwnerProof = copy(owner), crewReplacementSourceKey = key }
        for _, field in ipairs(headers) do view.raw[field] = raw[field] end
        return view, nil
    end
    local function plan(view, settings, funded)
        if type(settings) ~= "table" or settings.enabled ~= true then return nil, "Crew replacement disabled" end
        if settings.policy ~= nil and settings.policy ~= "Bounded replacement" then return nil, "Native autoroll start remains blocked" end
        if type(view) ~= "table" or view.sourceKey ~= key or not identity(view, view)
            or type(view.roster) ~= "table" or type(view.empty) ~= "table" or not integer(view.home, 0, 45)
            or not number(view.cash, 0, MAX) or not number(view.serverNow, 0, MAX) or not integer(view.hirePct, -25, 25)
            or not integer(settings.slot, 2, 46) or not tiers[settings.tier]
            or not integer(settings.targetRarity, 1, 8) or not integer(settings.maxDismissRarity, 1, 8)
            or not integer(settings.cashReserve, 0, MAX) or not integer(settings.minHome, 0, 45)
            or not integer(settings.maxCost, 0, MAX) or not integer(settings.maxSpend, 0, MAX)
            or not integer(settings.maxAttempts, 0, 1000) or settings.allowDismiss ~= true
            or not integer(view.attempted, 0, 1000) or not integer(view.spent, 0, MAX)
            or not text(view.ownerId, 120) or view.ownerSlot ~= settings.slot then
            return nil, "Explicit limits, durable usage and exclusive prepared-member owner proof required"
        end
        local tier, row = tiers[settings.tier], view.roster[settings.slot]
        if not row then return nil, "Selected Crew slot unavailable" end
        local odds, chance = view.lucky and tier.oddsLucky or tier.odds, 0
        for rarity = settings.targetRarity, 8 do chance = chance + odds[rarity] end
        local cost = math.max(1, math.floor(tier.cost * (100 + view.hirePct) / 100 + 0.5))
        local attemptedBefore, spentBefore = view.attempted, view.spent
        local targetSignature = signature(row)
        if funded then
            if type(funded) ~= "table" or not integer(funded.attemptedBefore, 0, 999)
                or not integer(funded.spentBefore, 0, MAX) or not integer(funded.cost, 1, MAX)
                or not text(funded.targetSignature, 32768)
                or view.ownerId ~= funded.ownerId or #view.empty ~= 1 or view.empty[1] ~= settings.slot
                or view.attempted ~= funded.attemptedBefore + 1 or view.spent ~= funded.spentBefore
                or cost ~= funded.cost or view.cityId ~= funded.cityId or view.familyId ~= funded.familyId
                or view.rulerId ~= funded.rulerId or view.hirePct ~= funded.hirePct then
                return nil, "Exact funded sole-empty target, cycle usage and unchanged quote required"
            end
            attemptedBefore, spentBefore, targetSignature = funded.attemptedBefore, funded.spentBefore, funded.targetSignature
        else
            if #view.empty > 0 then return nil, "Hire an existing empty slot before dismissing anyone" end
            if not selected(row, view.serverNow) or row.rarity >= settings.targetRarity
                or row.rarity > settings.maxDismissRarity or view.home - 1 < settings.minHome then
                return nil, "Selected member is protected or target/minimum home count reached"
            end
            for slot, other in ipairs(view.roster) do
                if slot ~= settings.slot and (row.healId and other.healId == row.healId
                    or not row.healId and signature(other) == targetSignature) then
                    return nil, "Ambiguous Crew target fingerprint"
                end
            end
        end
        if chance <= 0 or attemptedBefore >= settings.maxAttempts or cost > settings.maxCost
            or spentBefore + cost > settings.maxSpend or view.cash - cost < settings.cashReserve then
            return nil, "Unattainable target or replacement funding/attempt limit"
        end
        local kind = funded and "crewReplacementHire" or "crewReplacementDismiss"
        local intent = { kind = kind, slot = settings.slot, tier = settings.tier, targetRarity = settings.targetRarity,
            maxDismissRarity = settings.maxDismissRarity, cashReserve = settings.cashReserve, minHome = settings.minHome,
            maxCost = settings.maxCost, maxSpend = settings.maxSpend, maxAttempts = settings.maxAttempts,
            allowDismiss = true, attemptedBefore = attemptedBefore, spentBefore = spentBefore, cost = cost,
            sourceKey = key, ownerId = view.ownerId, targetSignature = targetSignature,
            rosterSignature = view.rosterSignature, cityId = view.cityId, familyId = view.familyId,
            rulerId = view.rulerId, hirePct = view.hirePct, decreeRevision = view.decreeRevision }
        local proposal = { feature = "crewRoll", actionKey = "crew-replacement:" .. view.ownerId .. ":"
            .. attemptedBefore .. ":" .. settings.slot .. ":" .. (funded and "hire" or "dismiss"),
            resources = funded and { cash = cost } or {}, intent = intent }
        for _, field in ipairs({ "session", "account", "place", "release", "revision" }) do proposal[field] = view[field] end
        return proposal, nil
    end
    result.propose = function(view, settings) return plan(view, settings) end
    result.FundedHire = function(raw, funded)
        local view, reason = result.read(raw, raw)
        if not view or type(funded) ~= "table" then return nil, reason or "Funded dismissal intent required" end
        return plan(view, settingsFrom(funded), funded)
    end
    result.capture = function(proposal, before)
        local intent = type(proposal) == "table" and proposal.intent
        local view = result.read(before, before)
        if not view or type(intent) ~= "table" or not identity(proposal, view) or proposal.revision ~= view.revision
            or proposal.feature ~= "crewRoll" then return nil, "Crew replacement baseline changed" end
        local funded = intent.kind == "crewReplacementHire" and intent or nil
        local expected = plan(view, settingsFrom(intent), funded)
        if not expected or expected.actionKey ~= proposal.actionKey or not same(expected.intent, intent)
            or not same(expected.resources, proposal.resources) then return nil, "Crew target, ownership, funding or limits changed" end
        return { before = copy(view.raw), intent = copy(intent), actionKey = proposal.actionKey }, nil
    end
    result.ValidBaseline = function(proposal, baseline)
        if type(baseline) ~= "table" or not copy(baseline) then return false end
        local captured = result.capture(proposal, baseline.before)
        return captured ~= nil and same(captured, baseline)
    end
    result.reconcile = function(proposal, baseline, after, reply, restart)
        if not result.ValidBaseline(proposal, baseline) or type(reply) ~= "table"
            or not identity(baseline.before, after, restart) then return "pending" end
        local current = result.read(after, after)
        local prior = result.read(baseline.before, baseline.before)
        if not current or not prior or current.serverNow <= prior.serverNow
            or after.session == prior.session and after.revision <= prior.revision then return "pending" end
        if current.size ~= prior.size then return "pending" end
        local intent, target = baseline.intent, current.roster[baseline.intent.slot]
        for slot, row in ipairs(prior.roster) do
            if slot ~= intent.slot and not same(row, current.roster[slot]) then return "pending" end
        end
        if reply.pending == true then return "pending" end
        if reply.ok == false then return current.rosterSignature == prior.rosterSignature and current.cash == prior.cash and "rejected" or "pending" end
        if reply.ok ~= true or reply.pending == true or reply.code == "rate_limited" then return "pending" end
        if intent.kind == "crewReplacementDismiss" then
            return next(target) == nil and current.cash == prior.cash and "confirmed" or "pending"
        end
        local returned = reply.member
        if (reply.index ~= nil and reply.index ~= intent.slot) or type(returned) ~= "table"
            or not text(returned.name, 64) or not integer(returned.rarity, 1, 8)
            or not integer(returned.atk, 0, MAX) or not integer(returned.def, 0, MAX)
            or not selected(target, current.serverNow) or current.cash ~= prior.cash - intent.cost then return "pending" end
        for _, field in ipairs({ "name", "rarity", "atk", "def" }) do if target[field] ~= returned[field] then return "pending" end end
        if returned.healId ~= nil and returned.healId ~= target.healId then return "pending" end
        return "confirmed"
    end
    result.evaluate = function(proposal, before, after, reply, baseline)
        if type(baseline) ~= "table" or not identity(before, baseline.before) then return "pending" end
        for _, field in ipairs(headers) do if before[field] ~= baseline.before[field] then return "pending" end end
        return result.reconcile(proposal, baseline, after, reply, false)
    end
    return result, nil
end
function CrewReplacement.describe(proposal)
    local intent = type(proposal) == "table" and proposal.intent
    if type(intent) ~= "table" or proposal.feature ~= "crewRoll" or intent.allowDismiss ~= true
        or not integer(intent.slot, 2, 46) or not text(intent.tier, 64) or not intent.tier:match("^[%w_]+$")
        or not integer(intent.cost, 1, MAX) or not integer(intent.maxCost, intent.cost, MAX)
        or not integer(intent.cashReserve, 0, MAX) or not integer(intent.maxSpend, intent.cost, MAX)
        or not integer(intent.spentBefore, 0, intent.maxSpend - intent.cost)
        or not integer(intent.maxAttempts, 1, 1000) or not integer(intent.attemptedBefore, 0, intent.maxAttempts - 1)
        or not integer(intent.targetRarity, 1, 8) or not integer(intent.maxDismissRarity, 1, 8)
        or not integer(intent.minHome, 0, 45) or not text(intent.targetSignature, 32768)
        or not text(intent.rosterSignature, 32768) or not text(intent.ownerId, 120)
        or type(intent.sourceKey) ~= "string" or #intent.sourceKey ~= 64 or not intent.sourceKey:match("^[%x]+$") then
        return nil, "Reviewed funded Crew replacement required"
    end
    local allowed = { kind = true, slot = true, tier = true, targetRarity = true, maxDismissRarity = true,
        cashReserve = true, minHome = true, maxCost = true, maxSpend = true, maxAttempts = true,
        allowDismiss = true, attemptedBefore = true, spentBefore = true, cost = true, sourceKey = true,
        ownerId = true, targetSignature = true, rosterSignature = true, cityId = true, familyId = true,
        rulerId = true, hirePct = true, decreeRevision = true }
    for field in pairs(intent) do if not allowed[field] then return nil, "Unknown replacement intent field" end end
    if not text(intent.cityId, 128) or type(intent.familyId) ~= "string" or #intent.familyId > 200
        or type(intent.rulerId) ~= "string" or #intent.rulerId > 200 or not integer(intent.hirePct, -25, 25)
        or not integer(intent.decreeRevision, 0, MAX) then return nil, "Current native hire quote identity required" end
    if intent.kind == "crewReplacementDismiss" and same(proposal.resources, {}) then
        return { remote = "CrewAction", method = "InvokeServer", arity = 4, args = { "dismiss", intent.slot },
            source = "saved CrewTab ordinary dismissal; snapshot-only identity guard" }, nil
    elseif intent.kind == "crewReplacementHire" and same(proposal.resources, { cash = intent.cost }) then
        return { remote = "CrewAction", method = "InvokeServer", arity = 4, args = { "hire", intent.tier, intent.cost },
            source = "saved CrewTab quoted ordinary hire; no destination slot argument" }, nil
    end
    return nil, "No reviewed Crew replacement call"
end
return CrewReplacement
