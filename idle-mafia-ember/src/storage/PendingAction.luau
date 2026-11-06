-- Data for reconciliation only. Never serializes a callback, capability or replay arm.
local PendingAction = {}
local MAX = 9007199254740991
local identity = {"session", "account", "place", "release"}
local function finite(value) return type(value) == "number" and value == value and math.abs(value) <= MAX end
local function text(value) return type(value) == "string" and #value > 0 and #value <= 1000 end
local function plain(value) return type(value) == "table" and getmetatable(value) == nil end
local function convert(value, decode)
    local seen, nodes, bytes = {}, 0, 0
    local function walk(child, depth)
        nodes = nodes + 1
        if nodes > 24000 or depth > 12 then error("Recovery data exceeds node/depth limit") end
        local kind = type(child)
        if kind == "string" then
            bytes = bytes + #child
            if #child > 16384 then error("Recovery string too large") end
        elseif kind == "number" then
            if not finite(child) then error("Recovery number invalid") end
            bytes = bytes + #tostring(child)
        elseif kind ~= "boolean" and kind ~= "table" then error("Recovery value invalid") end
        if bytes > 262144 then error("Recovery data exceeds byte limit") end
        if kind ~= "table" then return child end
        if seen[child] or getmetatable(child) ~= nil then error("Recovery table invalid") end
        seen[child] = true
        local source, output = child, {}
        if decode then
            if type(child.entries) ~= "table" then error("Recovery encoding invalid") end
            for field in pairs(child) do if field ~= "entries" then error("Unknown recovery encoding field") end end
            source = child.entries
        end
        for key, entry in pairs(source) do
            local encoded, restored
            if decode then
                if type(key) ~= "string" or #key > 1002 then error("Invalid encoded recovery key") end
                local prefix, raw = key:sub(1, 2), key:sub(3)
                if prefix == "s:" then restored = raw
                elseif prefix == "n:" then
                    restored = tonumber(raw)
                    if not finite(restored) or restored % 1 ~= 0 or tostring(restored) ~= raw then error("Invalid numeric recovery key") end
                else error("Unknown recovery key kind") end
                encoded = key
            elseif type(key) == "string" and #key <= 1000 then encoded = "s:" .. key
            elseif finite(key) and key % 1 == 0 then encoded = "n:" .. tostring(key)
            else error("Recovery key invalid") end
            bytes = bytes + #encoded + 16 -- Includes conservative JSON wrapper overhead.
            if bytes > 262144 then error("Recovery data exceeds byte limit") end
            output[decode and restored or encoded] = walk(entry, depth + 1)
        end
        seen[child] = nil
        return decode and output or {entries = output}
    end
    local ok, result = pcall(walk, value, 0)
    return ok and result or nil
end
-- Version 2 stores a bounded acyclic table graph, with a shared typed-key
-- dictionary. No outcome inputs are dropped; data/native aliases survive JSON.
local function dense(value)
    if not plain(value) or #value > 24000 then error("Invalid recovery array") end
    local count = 0
    for key in pairs(value) do
        if not finite(key) or key % 1 ~= 0 or key < 1 or key > #value then error("Invalid recovery array key") end
        count = count + 1
    end
    if count ~= #value then error("Sparse recovery array") end
    return count
end
local function restoreKey(key)
    if type(key) ~= "string" or #key > 1002 then error("Invalid encoded recovery key") end
    local prefix, raw = key:sub(1, 2), key:sub(3)
    if prefix == "s:" then return raw end
    local result = prefix == "n:" and tonumber(raw) or nil
    if not finite(result) or result % 1 ~= 0 or tostring(result) ~= raw then error("Invalid numeric recovery key") end
    return result
end
local function storeKey(key)
    if type(key) == "string" and #key <= 1000 then return "s:" .. key end
    if finite(key) and key % 1 == 0 then return "n:" .. tostring(key) end
    error("Recovery key invalid")
end
local function stringBytes(value)
    if type(value) ~= "string" then error("Recovery string invalid") end
    local bytes = 2 -- JSON quotes; charge Unicode escapes per code point, not UTF-8 byte.
    for _, code in utf8.codes(value) do
        if code < 32 then bytes = bytes + 6
        elseif code == 34 or code == 47 or code == 92 then bytes = bytes + 2
        elseif code < 128 then bytes = bytes + 1
        elseif code <= 65535 then bytes = bytes + 6
        else bytes = bytes + 12 end
    end
    return bytes
end
local function primitiveBytes(value)
    local kind = type(value)
    if kind == "string" and #value <= 16384 then return stringBytes(value) end
    if kind == "boolean" then return value and 4 or 5 end
    if finite(value) then
        -- Integers have an exact bounded decimal form. Round-trip precision plus two punctuation bytes covers a finite
        -- fractional double's JSON decimal/scientific representation.
        if value % 1 == 0 then return #string.format("%.0f", value) end
        return math.max(#tostring(value), #string.format("%.17g", value)) + 2
    end
    error("Recovery value invalid")
end
local function compact(value, decode)
    local function convertGraph()
        local keys, tables, keyIds, cache, used = {}, {}, {}, {}, {}
        local bytes, edges = #'{"version":2,"payload":{"keys":[],"tables":[]}}', 0
        local function charge(amount)
            bytes = bytes + amount
            if bytes > 262144 then error("Recovery data exceeds byte limit") end
        end
        if decode then
            if not plain(value) then error("Invalid recovery graph") end
            for key in pairs(value) do if key ~= "keys" and key ~= "tables" then error("Unknown recovery graph field") end end
            local keyCount = dense(value.keys)
            if dense(value.tables) < 1 then error("Missing recovery root") end
            tables = value.tables
            for index = 1, keyCount do
                local encoded = value.keys[index]
                local restored = restoreKey(encoded)
                if keyIds[encoded] then error("Duplicate recovery key") end
                keyIds[encoded], keys[index] = index, restored
                charge(stringBytes(encoded) + 1)
            end
        end
        local function walk(child, depth)
            if depth > 12 then error("Recovery data exceeds depth limit") end
            local source, index, existing
            if decode then
                index, source, existing = child, tables[child], cache[child]
            else
                if not plain(child) then error("Recovery table invalid") end
                existing = cache[child]
                if not existing then
                    index = #tables + 1
                    if index > 24000 then error("Recovery data exceeds node limit") end
                    tables[index] = {}
                else index = existing.index end
                source = child
            end
            if existing then
                if existing.active or depth + existing.height > 12 then error("Cyclic or deep recovery graph") end
                return existing
            end
            if not plain(source) then error("Invalid recovery entries") end
            local result = {index = index, active = true, nodes = 1, height = 0, value = {}}
            cache[decode and index or child] = result
            charge(3) -- Table braces and a conservative array separator.
            local order = {}
            for key in pairs(source) do
                order[#order + 1] = key
                if #order >= 24000 then error("Recovery data exceeds node limit") end
            end
            if not decode then
                -- Stable IDs keep Copy and reply updates within the same byte
                -- accounting regardless of input insertion order or JSON reload.
                table.sort(order, function(a, b) return storeKey(a) < storeKey(b) end)
            end
            for _, key in ipairs(order) do
                local entry = source[key]
                edges = edges + 1
                if edges >= 24000 then error("Recovery data exceeds node limit") end
                local keyIndex, storedKey, restored
                if decode then
                    keyIndex = type(key) == "string" and tonumber(key) or nil
                    if not finite(keyIndex) or keyIndex % 1 ~= 0 or keyIndex < 1
                        or keyIndex > #keys or tostring(keyIndex) ~= key then error("Invalid recovery key reference") end
                    restored, used[keyIndex] = keys[keyIndex], true
                    storedKey = key
                else
                    local encoded = storeKey(key)
                    keyIndex = keyIds[encoded]
                    if not keyIndex then
                        keyIndex = #keys + 1
                        keys[keyIndex], keyIds[encoded] = encoded, keyIndex
                        charge(stringBytes(encoded) + 1)
                    end
                    storedKey = tostring(keyIndex)
                end
                charge(#storedKey + 4) -- Quoted dictionary index, colon, comma.
                local encoded, restoredValue, nodes, height = entry, entry, 1, 0
                if type(entry) == "table" then
                    local reference = entry
                    if decode then
                        if not plain(entry) then error("Invalid recovery reference") end
                        for field in pairs(entry) do if field ~= 1 then error("Unknown recovery reference field") end end
                        reference = entry[1]
                        if not finite(reference) or reference % 1 ~= 0 or reference < 1
                            or reference > #tables then error("Invalid recovery table reference") end
                    end
                    local nested = walk(reference, depth + 1)
                    encoded, restoredValue = {nested.index}, nested.value
                    nodes, height = nested.nodes, nested.height
                    charge(#tostring(nested.index) + 2)
                else charge(primitiveBytes(entry)) end
                result.nodes, result.height = result.nodes + nodes, math.max(result.height, height + 1)
                if result.nodes > 24000 or depth + result.height > 12 then error("Recovery data exceeds node/depth limit") end
                if decode then result.value[restored] = restoredValue
                else tables[index][storedKey] = encoded end
            end
            result.active = false
            return result
        end
        local root = walk(decode and 1 or value, 0)
        if decode then
            for index = 1, #keys do if not used[index] then error("Unused recovery key") end end
            for index = 1, #tables do if not cache[index] then error("Unused recovery table") end end
            return root.value
        end
        return {keys = keys, tables = tables}
    end
    local ok, result = pcall(convertGraph)
    return ok and result or nil
end
-- Some legacy scalar arrays are smaller in v1 than in the key dictionary.
-- Only fresh, logically bounded v1 conversions can use this fallback, and
-- their actual JSON punctuation/escaping still must fit the same byte cap.
local function legacyFits(encoded)
    local bytes = #'{"version":1,"payload":}'
    local function walk(value)
        if type(value) == "table" then
            bytes = bytes + #'{"entries":{}}'
            for key, child in pairs(value.entries) do
                bytes = bytes + stringBytes(key) + 2 -- Colon and comma.
                if bytes > 262144 then error("Recovery data exceeds byte limit") end
                walk(child)
            end
        else bytes = bytes + primitiveBytes(value) end
        if bytes > 262144 then error("Recovery data exceeds byte limit") end
    end
    local ok = pcall(walk, encoded)
    return ok
end
local function valid(data, record)
    if type(data) ~= "table" or type(data.proposal) ~= "table" or type(data.before) ~= "table"
        or type(data.baseline) ~= "table" then return false end
    for key in pairs(data) do if key ~= "proposal" and key ~= "before" and key ~= "baseline" and key ~= "reply" then return false end end
    if data.reply ~= nil and type(data.reply) ~= "table" then return false end
    local proposal, before = data.proposal, data.before
    if proposal.requestId ~= nil and (not finite(proposal.requestId)
        or proposal.requestId < 1 or proposal.requestId % 1 ~= 0) then return false end
    for _, key in ipairs(identity) do
        if not text(proposal[key]) or proposal[key] ~= before[key] then return false end
    end
    if not finite(proposal.revision) or proposal.revision < 0 or proposal.revision % 1 ~= 0
        or proposal.revision ~= before.revision or not finite(before.capturedAt) or before.capturedAt < 0
        or type(before.native) ~= "table" or before.native.fullSync ~= true
        or not text(proposal.feature) or not text(proposal.actionKey)
        or type(proposal.intent) ~= "table" or not text(proposal.intent.kind)
        or type(proposal.resources) ~= "table" then return false end
    for key, value in pairs(proposal.intent) do
        if not text(key) or (type(value) ~= "string" and type(value) ~= "boolean" and not finite(value)) then return false end
    end
    for key, amount in pairs(proposal.resources) do if not text(key) or not finite(amount) or amount < 0 then return false end end
    if record then
        if proposal.requestId ~= record.requestId then return false end
        for _, key in ipairs({"account", "place", "release", "feature", "actionKey"}) do
            if proposal[key] ~= record[key] then return false end
        end
        if type(record.resources) ~= "table" then return false end
        for key, amount in pairs(proposal.resources) do if record.resources[key] ~= amount then return false end end
        for key, amount in pairs(record.resources) do if proposal.resources[key] ~= amount then return false end end
    end
    return true
end
-- A Heist recovery needs its original outcome inputs, not every unrelated
-- catalog/native history in the live planning snapshot. Keep the existing
-- serializer limits and preserve all fields actually read by the four evidences.
local heistKinds = {heists = "heistStart", favors = "favorHelp",
    sabotage = "heistSabotage", heistCollect = "heistCollect"}
local function selectedFields(source, fields)
    local result = {}
    for _, field in ipairs(fields) do result[field] = source[field] end
    return result
end
local function heistBefore(proposal, before)
    if not plain(before) or not plain(before.native) or not plain(before.heistBoardProof)
        or not plain(before.heistBoardProof.board) then return nil end
    local native, proof = before.native, before.heistBoardProof
    local board, kind = proof.board, proposal.intent.kind
    if not plain(board.rows) then return nil end
    local selected, count = nil, 0
    local needsRow = kind == "favorHelp" or kind == "heistSabotage"
    for index, row in ipairs(board.rows) do
        if index > 256 or not plain(row) then return nil end
        count = index
        -- Lua equality deliberately distinguishes numeric IDs from text IDs.
        if needsRow and row.id == proposal.intent.rowId then
            if selected ~= nil then return nil end
            selected = row
        end
    end
    for index in pairs(board.rows) do
        if not finite(index) or index % 1 ~= 0 or index < 1 or index > count then return nil end
    end
    if needsRow and (selected == nil or not (text(proposal.intent.rowId)
        or finite(proposal.intent.rowId) and proposal.intent.rowId >= 1 and proposal.intent.rowId % 1 == 0)) then return nil end
    local savedNative = selectedFields(native, {"fullSync", "serverNow"})
    if kind == "heistStart" then
        if not plain(native.pools) then return nil end
        savedNative.level, savedNative.cash = native.level, native.cash
        savedNative.pools = selectedFields(native.pools, {"energy"})
    elseif kind == "heistCollect" then
        for _, field in ipairs({"cash", "xp", "level", "maxLevel", "prestige", "inventory", "inventoryBound"}) do
            savedNative[field] = native[field]
        end
    else
        -- These exact scalars/maps comprise Favor/Sabotage knownResources.
        for _, field in ipairs({"cash", "xp", "level", "banked", "respect", "skillPoints",
            "paidMedals", "prestige", "maxLevel", "xpBoostEnd", "pools", "stats",
            "inventory", "inventoryBound", "collection", "collectionBound"}) do
            savedNative[field] = native[field]
        end
    end
    -- Sabotage dispatch binds the local Family identity; retain only that ID
    -- for exact saved recapture. Older missing membership stays unknown.
    if kind == "heistSabotage" and plain(native.family) then
        savedNative.family = selectedFields(native.family, {"id"})
    end
    local savedProof, savedBoard = {}, {}
    for field, value in pairs(proof) do savedProof[field] = value end
    for field, value in pairs(board) do if field ~= "rows" then savedBoard[field] = value end end
    -- Board metadata/result/provenance remain complete. Unselected rows are
    -- selection inputs; no reward/result fields or unknown values are defaulted.
    savedBoard.rows = selected and {selected} or {}
    savedProof.board = savedBoard
    local saved = selectedFields(before, {"session", "account", "place", "release", "revision", "capturedAt",
        "heistProtocolProof", "heistCatalog", "catalogKey", "favorUsageProof", "sabotageUsageProof", "localUserIdProof"})
    if kind == "heistSabotage" and proposal.intent.ownerProfileRequired == true then
        local ownerProof, owner = before.sabotageOwnerProof, nil
        if not plain(ownerProof) or not plain(ownerProof.header) or not plain(ownerProof.policy)
            or not plain(ownerProof.rows) or #ownerProof.rows > 256 then return nil end
        local size = 0
        for index, row in ipairs(ownerProof.rows) do
            if not plain(row) then return nil end
            size = index
            if row.rowId == proposal.intent.rowId then
                if owner ~= nil then return nil end
                owner = row
            end
        end
        for index in pairs(ownerProof.rows) do
            if not finite(index) or index % 1 ~= 0 or index < 1 or index > size then return nil end
        end
        if not owner then return nil end
        saved.sabotageOwnerProof = selectedFields(ownerProof, {"header", "sourceKey", "ownFamilyId", "policy"})
        saved.sabotageOwnerProof.rows = {owner}
    end
    saved.native, saved.heistBoardProof = savedNative, savedProof
    return saved
end

-- Recall's independently durable baseline owns the exact roster/deployment.
-- Preserve the original raw inputs too so Runtime.Capture/ReadState can recapture
-- that same baseline; unrelated player catalogs/history do not enter this file.
local function recallBefore(before)
    if not plain(before) or not plain(before.native) or not plain(before.native.family)
        or not plain(before.native.crew) or #before.native.crew < 2 or #before.native.crew > 46 then return nil end
    local native, crew, count = before.native, {}, 0
    for index, row in ipairs(native.crew) do
        if not plain(row) then return nil end
        count = index
        crew[index] = selectedFields(row, {"name", "rarity", "healId", "train", "duty", "dutyToken", "dutyAt",
            "injuredUntil", "recalledUntil", "training", "rolling", "recalling", "stationed", "dutyPending", "dutyRemapPending",
            "weapon", "armor", "vehicle"})
    end
    for index in pairs(native.crew) do
        if not finite(index) or index % 1 ~= 0 or index < 1 or index > count then return nil end
    end
    local saved = selectedFields(before, {"session", "account", "place", "release", "revision", "capturedAt",
        "territoryDistrict", "recallOwnerProof", "stationReservationProof"})
    saved.native = selectedFields(native, {"fullSync", "serverNow", "userId"})
    saved.native.family, saved.native.crew = selectedFields(native.family, {"id"}), crew
    return saved
end

-- Ordinary stationing shares exact roster custody with Recall and also
-- rechecks its owned map, catalog and original home/defender reservations.
local function stationBefore(proposal, before)
    local saved = recallBefore(before)
    if not saved then return nil end
    saved.recallOwnerProof = nil
    saved.territoryMap, saved.stationCatalogProof = before.territoryMap, before.stationCatalogProof
    for slot = 2, #before.native.crew do
        local observation = proposal.intent["unidentifiedHome" .. slot]
        if observation ~= nil then
            local row = before.native.crew[slot]
            if not text(observation) or #observation > 900 or not plain(row)
                or row.healId ~= nil or row.dutyToken ~= nil then return nil end
            -- The bounded graph converter below copies the exact original row.
            saved.native.crew[slot] = row
        end
    end
    return saved
end

-- Target catalogs are selection data, not durable outcome evidence. Keep only
-- this action's high-only membership; current full history stays in the live owner.
local function shopBefore(proposal, before)
    local id = proposal.intent.itemId
    local native = type(before) == "table" and before.native
    if type(id) ~= "string" or not plain(native) then return nil end
    local saved = selectedFields(before, {"session", "account", "place", "release", "revision", "capturedAt"})
    if before.shopUsageProof ~= nil then
        saved.shopUsageProof = selectedFields(before.shopUsageProof,
            {"session", "account", "place", "release", "revision", "capturedAt", "attempted", "spent"})
    end
    saved.native = selectedFields(native, {"fullSync", "serverNow", "level", "cash"})
    for _, origin in ipairs({"inventory", "inventoryBound", "collection", "collectionBound", "shopBought"}) do
        if native[origin] ~= nil then
            if not plain(native[origin]) then return nil end
            saved.native[origin] = {[id] = native[origin][id]}
        end
    end
    if type(native.autoBuyRules) == "table" then saved.native.autoBuyRules = selectedFields(native.autoBuyRules, {"on"}) end
    if type(before.shopCatalog) ~= "table" or type(before.shopCatalog.offers) ~= "table"
        or type(before.shopQuoteProof) ~= "table" or type(before.shopQuoteProof.stock) ~= "table"
        or type(before.shopQuoteProof.quotes) ~= "table" then return nil end
    if native.shopRotation ~= nil then
        if not plain(native.shopRotation) or native.shopRotation.bought ~= nil
            and not plain(native.shopRotation.bought) then return nil end
        saved.native.shopRotation = {slot = native.shopRotation.slot}
        if native.shopRotation.bought ~= nil then
            saved.native.shopRotation.bought = {[id] = native.shopRotation.bought[id]}
        end
    end
    saved.shopCatalog = selectedFields(before.shopCatalog, {"key", "release", "unlockLevel"})
    saved.shopCatalog.offers = {[id] = before.shopCatalog.offers[id]}
    saved.shopQuoteProof = selectedFields(before.shopQuoteProof,
        {"session", "account", "place", "release", "revision", "capturedAt", "catalogKey", "slot"})
    saved.shopQuoteProof.stock, saved.shopQuoteProof.quotes = {[id] = before.shopQuoteProof.stock[id]}, {[id] = before.shopQuoteProof.quotes[id]}
    return saved
end

-- Ordinary Job evidence needs its complete quote catalog and mastery rules,
-- original Energy and selected counters, not other tabs' maps/native history.
local function jobBefore(proposal, before)
    local native, id = before.native, proposal.intent.targetId
    if not plain(native) or not plain(native.pools) or not plain(native.jobs)
        or type(id) ~= "string" then return nil end
    local record = native.jobs[id]
    if record ~= nil and not plain(record) then return nil end
    local saved = selectedFields(before, {"session", "account", "place", "release", "revision", "capturedAt",
        "catalogKey", "jobCatalog", "masteryRules"})
    saved.native = selectedFields(native, {"fullSync", "serverNow", "userId", "autoJob", "level"})
    saved.native.pools = selectedFields(native.pools, {"energy"})
    saved.native.jobs = {}
    if record then saved.native.jobs[id] = selectedFields(record, {"completions", "masteryTier", "masteryProgress"}) end
    return saved
end

-- Family evidence reads only its scoped catalog/proofs, personal Gold custody,
-- exact balances and member identity. Other tabs' catalogs/history are not
-- recovery inputs and can prevent the complete native reply fitting the bound.
local function familyBefore(before)
    local native = type(before) == "table" and before.native
    if not plain(before) or not plain(native) or not plain(native.family)
        or not plain(native.pools) or not plain(native.inventory)
        or not plain(native.inventoryBound) then return nil end
    local saved = selectedFields(before, {"session", "account", "place", "release", "revision", "capturedAt",
        "familyContributionCatalog", "familyContributionProof", "familyUsageProof", "familyActorProof"})
    saved.native = selectedFields(native, {"fullSync", "serverNow", "userId", "cash"})
    saved.native.family = selectedFields(native.family, {"id"})
    saved.native.pools = selectedFields(native.pools, {"stamina"})
    for _, origin in ipairs({"inventory", "inventoryBound"}) do
        saved.native[origin] = selectedFields(native[origin], {"gold_bar"})
    end
    return saved
end

local function moneyBefore(before)
    local saved = selectedFields(before, {"session", "account", "place", "release", "revision", "capturedAt",
        "catalogKey", "bankConfig", "purchaseSavings", "fundingRequest"})
    saved.native = selectedFields(before.native, {"fullSync", "serverNow", "userId", "cash", "banked"})
    saved.native.derived = selectedFields(before.native.derived, {"noBankFees"})
    return saved
end

local function recoveryBefore(proposal, before)
    if type(proposal.intent) == "table" and plain(before) and plain(before.native)
        and before.native.fullSync == true and plain(before.bankConfig)
        and (proposal.feature == "bank" and proposal.intent.kind == "bankDeposit"
            or proposal.feature == "withdraw" and proposal.intent.kind == "purposeWithdrawal") then
        return moneyBefore(before)
    end
    if proposal.feature == "station" and type(proposal.intent) == "table"
        and proposal.intent.kind == "territoryStation" and plain(before)
        and plain(before.stationCatalogProof) and plain(before.territoryMap) then
        return stationBefore(proposal, before)
    end
    if proposal.feature == "jobs" and type(proposal.intent) == "table" and proposal.intent.kind == "job"
        and plain(before) and plain(before.jobCatalog) and plain(before.masteryRules) then
        return jobBefore(proposal, before)
    end
    if (proposal.feature == "familyCash" or proposal.feature == "familyGold" or proposal.feature == "familyStamina")
        and type(proposal.intent) == "table" and proposal.intent.kind == "familyContribution" then
        return familyBefore(before)
    end
    if proposal.feature == "shop" and type(proposal.intent) == "table"
        and proposal.intent.kind == "shopCashBuy" then return shopBefore(proposal, before) end
    if proposal.feature == "station" and type(proposal.intent) == "table"
        and proposal.intent.kind == "territoryRecall" then return recallBefore(before) end
    if heistKinds[proposal.feature] ~= nil and type(proposal.intent) == "table"
        and proposal.intent.kind == heistKinds[proposal.feature] then return heistBefore(proposal, before) end
    local ledger = type(before) == "table" and before.playerFightHistoryProof
    if type(ledger) ~= "table" or ledger.highValue == nil or getmetatable(before) ~= nil or getmetatable(ledger) ~= nil then return before end
    local saved, history = {}, {}
    for key, value in pairs(before) do saved[key] = value end
    for key, value in pairs(ledger) do if key ~= "highValue" then history[key] = value end end
    saved.playerFightHistoryProof = history
    local intent, high = proposal.intent, ledger.highValue
    if proposal.feature == "combat" and type(intent) == "table" and intent.highValueOnly == true
        and (intent.kind == "playerAttack" or intent.kind == "playerScout")
        and finite(intent.target) and intent.target >= 1 and intent.target % 1 == 0 then
        local targets = type(high) == "table" and high.targets
        local target = type(targets) == "table" and targets[tostring(intent.target)]
        history.highValue = {known = type(high) == "table" and high.known == true, targets = {}}
        if type(target) == "table" then history.highValue.targets[tostring(intent.target)] = {userId = target.userId} end
    end
    return saved
end
function PendingAction.Capture(proposal, before, baseline, reply)
    if type(proposal) ~= "table" then return nil, "Recovery proposal required" end
    local request = {}
    for _, key in ipairs({"session", "account", "place", "release", "revision", "feature", "actionKey", "resources", "intent", "requestId"}) do
        request[key] = proposal[key]
    end
    local data = {proposal = request, before = recoveryBefore(request, before), baseline = baseline, reply = reply}
    if not valid(data) then return nil, "Complete recovery intent and baseline required" end
    local encoded = compact(data, false)
    if encoded then return {version = 2, payload = encoded}, nil end
    encoded = convert(data, false)
    if not encoded or not legacyFits(encoded) then return nil, "Recovery data invalid or exceeds bounded storage" end
    return {version = 1, payload = encoded}, nil
end
function PendingAction.Decode(raw, record)
    if not plain(raw) or raw.version ~= 1 and raw.version ~= 2 then return nil end
    for key in pairs(raw) do if key ~= "version" and key ~= "payload" then return nil end end
    local data
    if raw.version == 1 then data = convert(raw.payload, true)
    else data = compact(raw.payload, true) end
    if not data or not valid(data, record) then return nil end
    return data
end
function PendingAction.Copy(raw, record)
    local data = PendingAction.Decode(raw, record)
    if not data then return nil end
    return PendingAction.Capture(data.proposal, data.before, data.baseline, data.reply)
end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
function PendingAction.WithReply(raw, record, reply)
    local data = PendingAction.Decode(raw, record)
    if not data or type(reply) ~= "table" then return nil, "Original pending data and table result required" end
    -- Validate/copy before comparison so cycles and capabilities cannot enter it.
    local encoded, reason = PendingAction.Capture(data.proposal, data.before, data.baseline, reply)
    if not encoded then return nil, reason end
    local candidate = PendingAction.Decode(encoded, record)
    if not candidate then return nil, "Returned result could not be decoded" end
    if data.reply ~= nil and not equal(data.reply, candidate.reply) then return nil, "A different result is already recorded" end
    return encoded, nil
end
function PendingAction.Same(first, second, record)
    local a, b = PendingAction.Decode(first, record), PendingAction.Decode(second, record)
    return a ~= nil and b ~= nil and equal(a, b)
end
return PendingAction
