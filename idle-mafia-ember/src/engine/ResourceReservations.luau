-- Shared custody is derived from trusted pending/store owners, never snapshot claims.
local ResourceReservations = {}
local MAX = 9007199254740991
local crewFeatures = {crew = true, crewGear = true, crewRoll = true, crewSort = true,
    crewHeal = true, crewTrain = true, crewHire = true, crewHealItems = true, station = true}
local itemFeatures = {crew = true, crewGear = true, crewRoll = true, cosmetics = true,
    chests = true, crewHealItems = true, restoratives = true, marketSell = true, marketFlip = true}
local scalarFunds = {cash = true, banked = true, skillPoints = true, energy = true, stamina = true, health = true}
local memberKinds = {crewGear = true, crewTrain = true, crewHeal = true,
    crewHealItems = true, crewHire = true, crewReplacementDismiss = true, crewReplacementHire = true}
local function number(value)
    return type(value) == "number" and value == value and value >= 0 and value <= MAX
end
local function integer(value) return number(value) and value % 1 == 0 end
local function text(value, maximum)
    return type(value) == "string" and #value > 0 and #value <= maximum and not value:find("%c")
end
local function empty()
    return {members = {}, items = {}, funds = {}, allCrew = false, allItems = false}
end
local function dense(raw, maximum)
    if type(raw) ~= "table" or #raw > maximum then return false end
    local size = 0
    for key in pairs(raw) do
        if not integer(key) or key < 1 or key > #raw then return false end
        size = size + 1
    end
    return size == #raw
end
function ResourceReservations.CopyClaims(raw)
    if type(raw) ~= "table" or type(raw.allCrew) ~= "boolean"
        or (raw.allItems ~= nil and type(raw.allItems) ~= "boolean") then return nil end
    for key in pairs(raw) do
        if key ~= "members" and key ~= "items" and key ~= "funds" and key ~= "allCrew" and key ~= "allItems" then return nil end
    end
    local result = empty()
    result.allCrew, result.allItems = raw.allCrew, raw.allItems == true
    for _, field in ipairs({"members", "items", "funds"}) do
        if type(raw[field]) ~= "table" then return nil end
        local count = 0
        for key, value in pairs(raw[field]) do
            count = count + 1
            if count > 128 or not text(key, 200) then return nil end
            if field == "members" then
                if value ~= true then return nil end
            elseif field == "items" then
                if not integer(value) or not (key:sub(1, 2) == "L:" or key:sub(1, 2) == "B:")
                    or not text(key:sub(3), 120) then return nil end
            elseif not number(value) then return nil end
            result[field][key] = value
        end
    end
    return result
end
local function member(claims, native, slot, allowEmpty)
    if not integer(slot) or slot < 1 or slot > 46 or type(native.crew) ~= "table" then return false end
    claims.members["slot:" .. slot] = true
    if slot == 1 then claims.members.player = true; return true end
    local row = native.crew[slot]
    if row == nil and allowEmpty then claims.allCrew = true; return true end
    if type(row) ~= "table" then return false end
    if not text(row.healId, 128) then claims.allCrew = true; return true end
    claims.members["id:" .. row.healId] = true
    for index, other in pairs(native.crew) do
        if not integer(index) or index < 1 or index > 46 or type(other) ~= "table" then return false end
        if index ~= slot and other.healId == row.healId then claims.allCrew = true end
    end
    return true
end
local function item(claims, id, amount, bound)
    if not text(id, 120) or not integer(amount) then return false end
    claims.items[(bound and "B:" or "L:") .. id] = amount
    claims.funds[id] = nil -- The origin-aware item claim replaces total-inventory exposure.
    return true
end
function ResourceReservations.ForProposal(proposal, raw)
    local native = type(raw) == "table" and raw.native
    local intent = type(proposal) == "table" and proposal.intent
    if type(native) ~= "table" or native.fullSync ~= true or type(intent) ~= "table"
        or type(proposal.resources) ~= "table" then return nil, "Current reservation input required" end
    local claims = empty()
    for key, value in pairs(proposal.resources) do claims.funds[key] = value end
    local kind = intent.kind
    if proposal.feature == "eventShop" and kind == "eventShopBuy" or proposal.feature == "bossShop" and kind == "bossShopBuy" or proposal.feature == "familyBossClaims" and kind == "familyBossClaim"
        or proposal.feature == "globalBossClaim" and kind == "globalBossClaim" then
        claims.allItems = true -- Keep newly awarded custody until purchase reconciliation.
    end
    if proposal.feature == "globalBossAttack" and kind == "globalBossAttack" then
        claims.funds.health = 0 -- Check held Health against the explicit 75% local buffer.
    end
    if proposal.feature == "bosses" and kind == "bossStageAttack" then
        if not integer(intent.hitBackMax) then return nil, "Boss health exposure unavailable" end
        claims.funds.health = intent.hitBackMax
    end
    if proposal.feature == "familyBossAttacks" and kind == "familyBossAttack" then
        if intent.uncalculatedHitBack == true then
            local health = type(native.pools) == "table" and native.pools.health
            local maximum = type(native.stats) == "table" and native.stats.maxHealth
            if not number(health) or not integer(maximum) or maximum < 1 or health ~= maximum then
                return nil, "Unknown Takedown damage requires full Health custody"
            end
            claims.funds.health = health -- Unknown damage keeps all Health held until exact reconciliation.
        else
            if not integer(intent.expectedHitBackMax) or intent.expectedHitBackMax < 1 then
                return nil, "Family hit-back exposure unavailable"
            end
            claims.funds.health = intent.expectedHitBackMax
        end
    end
    if kind == "crewReplacementDismiss" or kind == "crewReplacementHire" then
        if not number(intent.cost) then return nil, "Funded hire custody unavailable" end
        claims.funds.cash = intent.cost
    end
    if kind == "crewSort" or kind == "crewAutoEquip" then
        if type(native.crew) ~= "table" then return nil, "Current roster custody unavailable" end
        claims.allCrew = true
        claims.allItems = kind == "crewAutoEquip"
    elseif memberKinds[kind] or kind == "territoryStation" or kind == "territoryRecall" then
        local slot = kind == "territoryStation" and intent.memberSlot
            or kind == "territoryRecall" and intent.memberIndex or intent.slot
        if not member(claims, native, slot, kind == "crewHire" or kind == "crewReplacementHire") then
            return nil, "Current member reservation unavailable"
        end
        if kind=="crewTrain" then claims.allCrew=true end -- Preserve the one-member home backup until start is observed.
    end
    if kind == "territoryStation" then
        if not integer(intent.minHome) or intent.minHome > 45 or type(intent.homeSlots) ~= "string"
            or #intent.homeSlots > 134 or not number(native.serverNow) then return nil, "Exact home backup custody required" end
        local seen, slots = {}, {}
        for encoded in intent.homeSlots:gmatch("[^,]+") do
            local slot = tonumber(encoded)
            local row = slot and type(native.crew) == "table" and native.crew[slot]
            if not slot or tostring(slot) ~= encoded or not integer(slot) or slot < 2 or slot > 46
                or slot == intent.memberSlot or seen[slot] or type(row) ~= "table" or not text(row.healId,128)
                or intent["homeKey" .. slot] ~= "id:" .. row.healId or row.duty and row.duty ~= false
                or row.training ~= nil or row.rolling == true or row.dutyPending == true or row.dutyRemapPending == true
                or not number(row.injuredUntil or 0) or (row.injuredUntil or 0) > native.serverNow
                or not number(row.recalledUntil or 0) or (row.recalledUntil or 0) > native.serverNow
                or not member(claims,native,slot,false) or claims.allCrew then return nil, "Home backup custody changed" end
            seen[slot], slots[#slots + 1] = true, encoded
        end
        if #slots ~= intent.minHome or table.concat(slots, ",") ~= intent.homeSlots then
            return nil, "Home backup count changed"
        end
    end
    if kind == "marketCollectionWithdraw" then
        local collected=type(native.collection)=="table" and native.collection[intent.itemId]
        if proposal.feature~="marketSell" or not text(intent.itemId,120) or not integer(intent.quantity)
            or intent.quantity<1 or intent.quantity>999 or not integer(collected) or collected<intent.quantity
            or next(proposal.resources)~=nil then return nil,"Invalid Collection withdrawal custody" end
        claims.allItems=true -- One transfer holds inventory until its output origin is established.
    elseif kind == "marketList" then
        local loose = type(native.inventory) == "table" and native.inventory[intent.itemId]
        if loose == nil then loose = 0 end
        if (proposal.feature ~= "marketSell" and proposal.feature ~= "marketFlip")
            or not integer(intent.quantity) or intent.quantity < 1 or intent.quantity > 999
            or not integer(loose) or intent.quantity > loose
            or not text(intent.itemId, 120) or proposal.resources[intent.itemId] ~= intent.quantity
            or not item(claims, intent.itemId, intent.quantity, false) then
            return nil, "Invalid loose listing custody"
        end
        for id in pairs(proposal.resources) do
            if id ~= intent.itemId then return nil, "Unexpected listing resource" end
        end
    elseif kind == "collectionDonate" or kind == "chests" then
        if not item(claims, intent.itemId, intent.amount, false) then return nil, "Invalid loose item claim" end
    elseif kind == "crewHealItems" or kind == "restoratives" then
        if type(intent.fromBound) ~= "boolean" or not item(claims, intent.itemId, 1, intent.fromBound) then
            return nil, "Invalid consumable origin claim"
        end
    elseif kind == "crewGear" or kind == "cosmetics" then
        if not item(claims, intent.itemId, 1, false) then return nil, "Invalid owned equipment claim" end
        -- A native gear swap also returns the formerly equipped copy. Keep that incoming item
        -- protected while its exact identity/effect is still pending, including after a skip.
        if kind=="crewGear" then claims.allItems=true end
    elseif kind == "familyContribution" and intent.resource == "gold_bar" then
        if intent.allowNativeGoldPool ~= nil and type(intent.allowNativeGoldPool) ~= "boolean" then
            return nil, "Invalid Family Gold payment permission"
        end
        if intent.allowNativeGoldPool ~= true then
            if not item(claims, "gold_bar", intent.amount, false) then return nil, "Invalid loose Gold claim" end
        elseif proposal.feature ~= "familyGold" or not integer(intent.amount) or intent.amount < 1
            or proposal.resources.gold_bar ~= intent.amount then return nil, "Invalid native total-Gold claim" end
    elseif kind == "eventShopBuy" then
        if not item(claims, "event_medal", intent.price, true) then return nil, "Invalid earned medal claim" end
    elseif kind == "marketRent" then
        -- The native rental accepts combined Gold; its server chooses the pool.
        -- Preserve total-funds exposure so both origin-specific holders conflict.
        if proposal.feature ~= "marketRent" or not integer(intent.cost) or intent.cost < 1
            or proposal.resources.gold_bar ~= intent.cost then return nil, "Invalid total rental Gold claim" end
        for id in pairs(proposal.resources) do
            if id ~= "gold_bar" then return nil, "Unexpected rental resource" end
        end
    end
    local copied = ResourceReservations.CopyClaims(claims)
    return copied, not copied and "Invalid reservation claims" or nil
end
local function merge(total, claims)
    total.allCrew, total.allItems = total.allCrew or claims.allCrew, total.allItems or claims.allItems
    for key in pairs(claims.members) do total.members[key] = true end
    for _, field in ipairs({"items", "funds"}) do
        for key, value in pairs(claims[field]) do
            local amount = (total[field][key] or 0) + value
            if not number(amount) then return false end
            total[field][key] = amount
        end
    end
    return true
end
local function count(map, id)
    if type(map) ~= "table" then return nil end
    local value = map[id]
    if value == nil then value = 0 end
    return integer(value) and value or nil
end
local function balance(native, resource)
    if resource == "cash" or resource == "banked" or resource == "skillPoints" then
        return number(native[resource]) and native[resource] or nil
    end
    if resource == "energy" or resource == "stamina" or resource == "health" then
        local value = type(native.pools) == "table" and native.pools[resource]
        return number(value) and value or nil
    end
    local inventoryId = resource == "bossTokens" and "boss_token" or resource
    local loose, bound = count(native.inventory, inventoryId), count(native.inventoryBound, inventoryId)
    return loose ~= nil and bound ~= nil and loose + bound or nil
end
local function inScope(raw, scope, session)
    if type(raw) ~= "table" then return false end
    for _, key in ipairs({"account", "place", "release"}) do if raw[key] ~= scope[key] then return false end end
    return not session or raw.session == scope.session
end
function ResourceReservations.new(identity, records, providers)
    assert(type(identity) == "table" and type(records) == "function"
        and (providers == nil or type(providers) == "table"), "Missing reservation owners")
    local scope, sources = {}, {}
    for _, key in ipairs({"session", "account", "place", "release"}) do
        assert(text(identity[key], 200), "Invalid reservation scope")
        scope[key] = identity[key]
    end
    assert(dense(providers or {}, 32), "Invalid durable reservation providers")
    local ids = {}
    for _, source in ipairs(providers or {}) do
        assert(type(source) == "table" and text(source.id, 80) and type(source.read) == "function"
            and not ids[source.id], "Invalid durable reservation provider")
        ids[source.id] = true
        sources[#sources + 1] = {id = source.id, read = source.read}
    end
    local result = {}
    local function heldClaims(raw, proposal)
        if not inScope(raw, scope, true) then return nil, "Reservation scope changed" end
        local held, pendingClaims = empty(), {}
        local ok, pending = pcall(records)
        if not ok or not dense(pending, 256) then return nil, "Pending custody unavailable" end
        for _, record in ipairs(pending) do
            if not inScope(record, scope, false) or not text(record.feature, 80)
                or not text(record.actionKey, 1000) then return nil, "Pending custody scope changed" end
            if not proposal or record.actionKey ~= proposal.actionKey or record.feature ~= proposal.feature then
                local claims = record.custody and ResourceReservations.CopyClaims(record.custody)
                if record.custody == nil then
                    claims = empty()
                    claims.funds = record.resources
                    claims.allCrew = crewFeatures[record.feature] == true
                    claims.allItems = itemFeatures[record.feature] == true and next(record.resources or {}) == nil
                    claims = ResourceReservations.CopyClaims(claims)
                end
                if not claims or not merge(held, claims) then return nil, "Invalid pending custody" end
                local identity = #record.feature .. ":" .. record.feature .. record.actionKey
                if pendingClaims[identity] then return nil, "Duplicate pending custody" end
                pendingClaims[identity] = claims
            end
        end
        for _, source in ipairs(sources) do
            local read, value, why = pcall(source.read, raw)
            if not read or value == nil and why ~= nil then return nil, "Durable custody unavailable: " .. source.id end
            if value ~= nil then
                if not inScope(value, scope, false) or not text(value.feature, 80)
                    or value.actionKey ~= nil and not text(value.actionKey, 1000) then return nil, "Durable custody scope changed" end
                local claims = ResourceReservations.CopyClaims(value.claims)
                if not claims then return nil, "Invalid durable custody" end
                if not proposal or value.feature ~= proposal.feature or value.actionKey ~= proposal.actionKey then
                    -- A store and the generic checkpoint can describe the same
                    -- sent stage. Hold its union rather than charging twice.
                    local identity = value.actionKey and (#value.feature .. ":" .. value.feature .. value.actionKey)
                    local previous = identity and pendingClaims[identity]
                    if previous then
                        for _, field in ipairs({"items", "funds"}) do
                            for key, amount in pairs(claims[field]) do
                                claims[field][key] = math.max(0, amount - (previous[field][key] or 0))
                                previous[field][key] = math.max(amount, previous[field][key] or 0)
                            end
                        end
                    elseif identity then
                        pendingClaims[identity] = ResourceReservations.CopyClaims(claims)
                    end
                    if not merge(held, claims) then return nil, "Durable custody exceeds limits" end
                end
            end
        end
        return held, nil
    end
    function result:Held(raw)
        local revision, capturedAt = type(raw) == "table" and raw.revision, type(raw) == "table" and raw.capturedAt
        local held, reason = heldClaims(raw)
        if not held then return nil, reason end
        if not inScope(raw, scope, true) or raw.revision ~= revision or raw.capturedAt ~= capturedAt then
            return nil, "Reservation snapshot changed during capture"
        end
        return held, nil
    end
    function result:Check(proposal, raw)
        if not inScope(raw, scope, true) or not inScope(proposal, scope, true)
            or raw.revision ~= proposal.revision then return nil, "Reservation scope or revision changed" end
        local revision, capturedAt = raw.revision, raw.capturedAt
        local requested, reason = ResourceReservations.ForProposal(proposal, raw)
        if not requested then return nil, reason end
        local held, heldReason = heldClaims(raw, proposal)
        if not held then return nil, heldReason end
        if (proposal.feature == "combat" or proposal.feature == "warCombat")
            and proposal.intent.kind == "playerAttack" and (held.funds.health or 0) > 0 then
            return nil, "Player Health is held by another unresolved action"
        end
        if requested.allCrew or next(requested.members) ~= nil then
            for slot, row in pairs(raw.native.crew or {}) do
                if type(row) ~= "table" then return nil, "Native member custody invalid" end
                if row.training ~= nil or row.rolling == true then
                    if not member(held, raw.native, slot, false) then return nil, "Native member custody unavailable" end
                end
            end
            if (requested.allCrew and (held.allCrew or next(held.members) ~= nil))
                or (held.allCrew and next(requested.members) ~= nil) then return nil, "Crew roster is reserved" end
            for key in pairs(requested.members) do if held.members[key] then return nil, "Crew member is reserved" end end
        end
        if (requested.allItems and (held.allItems or next(held.items) ~= nil))
            or (held.allItems and next(requested.items) ~= nil) then return nil, "Inventory custody is reserved" end
        for key, amount in pairs(held.funds) do
            if requested.allItems and amount > 0 and not scalarFunds[key] then return nil, "Inventory custody is reserved" end
        end
        for key, needed in pairs(requested.items) do
            local reserved = (held.items[key] or 0) + (held.funds[key:sub(3)] or 0)
            if reserved > 0 then
                local available = count(key:sub(1, 2) == "B:" and raw.native.inventoryBound or raw.native.inventory, key:sub(3))
                if available == nil or needed + reserved > available then return nil, "Item copies are reserved" end
            end
        end
        for key, needed in pairs(requested.funds) do
            if held.allItems and needed > 0 and not scalarFunds[key] then return nil, "Inventory custody is reserved" end
            local inventoryId = key == "bossTokens" and "boss_token" or key
            local reserved = (held.funds[key] or 0) + (held.items["L:" .. inventoryId] or 0) + (held.items["B:" .. inventoryId] or 0)
            if key == "bossTokens" then reserved = reserved + (held.funds.boss_token or 0) end
            if key == "gold_bar" and (proposal.feature == "marketRent"
                or proposal.feature == "familyGold" and proposal.intent.kind == "familyContribution"
                    and proposal.intent.allowNativeGoldPool == true) then
                -- Either pool may pay the entire quote. Total solvency alone
                -- cannot protect an origin-specific claim in the smaller pool.
                for _, origin in ipairs({"L:", "B:"}) do
                    local originHeld = held.items[origin .. key] or 0
                    if originHeld > 0 then
                        local available = count(origin == "L:" and raw.native.inventory or raw.native.inventoryBound, key)
                        if available == nil or needed + originHeld > available then
                            return nil, "Native Gold payment origin is reserved"
                        end
                    end
                end
            end
            local floor=0
            if (proposal.feature == "familyCash" or proposal.feature == "familyStamina" or proposal.feature == "familyGold")
                and proposal.intent.kind == "familyContribution" and key == proposal.intent.resource then
                floor = proposal.intent.reserve
                if not integer(floor) then return nil, "Family contribution reserve unavailable" end
            elseif proposal.feature == "bossShop" and key == "bossTokens" then
                floor = proposal.intent.tokenReserve
                if not integer(floor) then return nil, "Boss Shop reserve unavailable" end
            elseif proposal.feature == "globalBossAttack" and key == "stamina" then
                floor = 1
            elseif proposal.feature == "globalBossAttack" and key == "health" then
                local maxHealth = type(raw.native.stats) == "table" and raw.native.stats.maxHealth
                if not number(maxHealth) or maxHealth < 1 then return nil, "Global Boss health buffer unavailable" end
                floor = maxHealth * 0.75
            elseif proposal.feature == "bosses" and key == "stamina" then
                floor = 1
            elseif proposal.feature == "familyBossAttacks" and key == "stamina" then
                floor = 1
            elseif proposal.feature == "familyBossAttacks" and key == "health" and proposal.intent.uncalculatedHitBack ~= true then
                local maximum = type(raw.native.stats) == "table" and raw.native.stats.maxHealth
                if not number(maximum) or maximum < 1 then return nil, "Family health reserve unavailable" end
                floor = math.max(20, maximum * 0.5)
            elseif proposal.feature == "bosses" and key == "health" then
                local maxHealth = type(raw.native.stats) == "table" and raw.native.stats.maxHealth
                if not number(maxHealth) or maxHealth < 1 then return nil, "Boss health reserve unavailable" end
                floor = maxHealth * 0.5
            elseif proposal.feature=="crewHeal" and key=="stamina" then
                floor=proposal.intent.staminaReserve
                if not integer(floor) then return nil,"Crew heal reserve unavailable" end
            elseif proposal.feature=="crewTrain" and key=="cash" then
                floor=proposal.intent.cashReserve
                if not integer(floor) then return nil,"Crew training reserve unavailable" end
            elseif proposal.feature=="crewHire" and key=="cash" then
                floor=proposal.intent.reserve
                if not integer(floor) then return nil,"Crew hire reserve unavailable" end
            elseif proposal.feature=="crewRoll" and key=="cash"
                and (proposal.intent.kind=="crewReplacementDismiss" or proposal.intent.kind=="crewReplacementHire") then
                floor=proposal.intent.cashReserve
                if not integer(floor) then return nil,"Crew replacement reserve unavailable" end
            elseif proposal.feature=="marketRent" and key=="gold_bar" then
                floor=proposal.intent.goldReserve
                if not integer(floor) then return nil,"Market rental reserve unavailable" end
            end
            if reserved>0 or floor>0 then
                local available=balance(raw.native,key)
                if available==nil or needed+reserved+floor>available then return nil,"Resource funding or reserve is held" end
            end
        end
        if not inScope(raw, scope, true) or raw.revision ~= revision or raw.capturedAt ~= capturedAt then
            return nil, "Reservation snapshot changed during capture"
        end
        return requested, nil
    end
    return result
end
return ResourceReservations
