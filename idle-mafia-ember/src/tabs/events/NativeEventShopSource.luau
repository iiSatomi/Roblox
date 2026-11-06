-- Inject the reviewed EventShop table and native shop/account attributes. No services or sends.
local NativeEventShopSource = {}
local MAX = 9007199254740991
local fields = { "session", "account", "place", "release", "revision", "capturedAt" }
local function number(value, low, high)
    return type(value) == "number" and value == value and value >= low and value <= high
end
local function integer(value, low, high) return number(value, low, high) and value % 1 == 0 end
local function id(value) return type(value) == "string" and #value > 0 and #value <= 120 and value:match("^[%w_%-]+$") ~= nil end
local function copy(value)
    if type(value) ~= "table" then return value end
    local result = {}
    for key, child in pairs(value) do result[key] = copy(child) end
    return result
end
local function same(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not same(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function header(raw, release)
    if type(raw) ~= "table" or raw.release ~= release or type(raw.native) ~= "table"
        or raw.native.fullSync ~= true or not number(raw.native.serverNow, 0, MAX)
        or not integer(raw.revision, 0, MAX) or not number(raw.capturedAt, 0, MAX) then return nil end
    local result = {}
    for _, field in ipairs(fields) do result[field] = raw[field] end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(result[field]) ~= "string" or #result[field] == 0 or #result[field] > 200 then return nil end
    end
    return result
end
local function catalog(definition)
    if type(definition) ~= "table" or definition.MEDAL ~= "event_medal"
        or not integer(definition.MAX_ITEM_COUNT, 1, 99) or type(definition.ROWS) ~= "table" then return nil end
    local rows, count = {}, 0
    for index, row in pairs(definition.ROWS) do
        count = count + 1
        if not integer(index, 1, 64) or type(row) ~= "table" or not id(row.key)
            or not id(row.item) or not id(row.kind) or not integer(row.price, 1, 1000000000)
            or rows[row.key] ~= nil then return nil end
        local amount = row.count == nil and 1 or row.count
        if not integer(amount, 1, definition.MAX_ITEM_COUNT) then return nil end
        rows[row.key] = { key = row.key, kind = row.kind, item = row.item,
            count = amount, price = row.price, supported = row.kind == "crate" or row.kind == "item" }
    end
    if count == 0 or count > 64 then return nil end
    for index = 1, count do if definition.ROWS[index] == nil then return nil end end
    return rows
end
function NativeEventShopSource.new(definition, readAttributes, fingerprint, release)
    local offers = catalog(definition)
    if not offers or type(readAttributes) ~= "function" or type(fingerprint) ~= "string"
        or #fingerprint ~= 64 or not fingerprint:match("^[%x]+$")
        or type(release) ~= "string" or #release == 0 or #release > 200 then
        return nil, "Reviewed EventShop rows and native attribute callback required"
    end
    local generation, closed, latest = 0, false, nil
    local result = { sourceKey = fingerprint:lower(), release = release }
    local function current(expected)
        if closed or not latest or expected ~= latest.sourceGeneration then return false end
        local captured = latest
        local ok, attributes = pcall(readAttributes)
        if not ok or type(attributes) ~= "table" or closed or latest ~= captured
            or generation ~= expected or not same(catalog(definition), offers)
            or attributes.GlobalEventShop ~= captured.open
            or attributes.GlobalEventShopEnd ~= captured.endsAt
            or (attributes.MWPaidRandomRestricted ~= nil and type(attributes.MWPaidRandomRestricted) ~= "boolean")
            or (attributes.MWPaidRandomRestricted ~= false) ~= captured.restricted then return false end
        if attributes.serverNow ~= nil and (not number(attributes.serverNow, captured.serverNow, MAX)
            or (captured.endsAt > 0 and attributes.serverNow >= captured.endsAt)) then return false end
        return true
    end
    function result:Enrich(snapshot)
        local bound = header(snapshot, release)
        if closed or not bound or not same(catalog(definition), offers) then return nil, "Current full Event Shop Sync required" end
        generation, latest = generation + 1, nil
        local capturedGeneration, serverNow = generation, snapshot.native.serverNow
        local ok, attributes = pcall(readAttributes)
        if not ok or type(attributes) ~= "table" or type(attributes.GlobalEventShop) ~= "boolean"
            or not number(attributes.GlobalEventShopEnd, 0, MAX)
            or (attributes.MWPaidRandomRestricted ~= nil and type(attributes.MWPaidRandomRestricted) ~= "boolean") then
            return nil, "Current native Event Shop attributes unavailable"
        end
        if closed or generation ~= capturedGeneration or not same(header(snapshot, release), bound)
            or snapshot.native.serverNow ~= serverNow then return nil, "Event Shop source changed during capture" end
        latest = { header = bound, sourceKey = fingerprint:lower(), release = release,
            sourceGeneration = generation, serverNow = serverNow, medal = "event_medal",
            offers = copy(offers), open = attributes.GlobalEventShop,
            endsAt = attributes.GlobalEventShopEnd, restricted = attributes.MWPaidRandomRestricted ~= false }
        local enriched = {}
        for key, value in pairs(snapshot) do enriched[key] = value end
        enriched.eventShopProof = copy(latest)
        return enriched, nil
    end
    function result:Read(raw, context)
        local bound = header(raw, release)
        local contextHeader = {}
        if type(context) == "table" then
            for _, field in ipairs(fields) do contextHeader[field] = context[field] end
        end
        if closed or not bound or not same(bound, contextHeader) or not latest
            or not same(raw.eventShopProof, latest) or not same(latest.header, bound)
            or latest.serverNow ~= raw.native.serverNow then
            return nil, "Event Shop proof is not from this current source and full Sync"
        end
        local expected = latest
        if not current(expected.sourceGeneration) or latest ~= expected
            or not same(header(raw, release), bound) or not same(raw.eventShopProof, expected)
            or raw.native.serverNow ~= expected.serverNow then
            return nil, "Current native Event Shop attributes or offers changed"
        end
        return copy(expected), nil
    end
    -- Historical source validation observes an already saved attempt; it cannot authorize emission.
    function result:ReadSaved(raw, context)
        local bound = header(raw, release)
        local proof = type(raw) == "table" and raw.eventShopProof
        local contextHeader = {}
        if type(context) == "table" then for _, field in ipairs(fields) do contextHeader[field] = context[field] end end
        if closed or not bound or not same(bound, contextHeader) or type(proof) ~= "table"
            or not same(proof.header, bound) or proof.sourceKey ~= self.sourceKey or proof.release ~= release
            or not integer(proof.sourceGeneration, 1, MAX) or proof.serverNow ~= raw.native.serverNow
            or proof.medal ~= "event_medal" or type(proof.open) ~= "boolean"
            or type(proof.restricted) ~= "boolean" or not number(proof.endsAt, 0, MAX)
            or not same(proof.offers, offers) or not same(catalog(definition), offers) then
            return nil, "Saved Event Shop source does not match reviewed terms"
        end
        return copy(proof), nil
    end
    function result:CanDispatch(proposal)
        local intent = type(proposal) == "table" and proposal.intent
        return type(intent) == "table" and proposal.feature == "eventShop"
            and intent.sourceKey == self.sourceKey and latest ~= nil and latest.open == true
            and current(intent.sourceGeneration)
    end
    function result:Close() closed, latest, generation = true, nil, generation + 1 end
    return result, nil
end
return NativeEventShopSource
