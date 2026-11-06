-- A native buy reply needs exact newer Gold and unbound-item custody.
local MarketBuyEvidence = {}

local function finite(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

local function text(value, maximum)
    return type(value) == "string" and #value > 0
        and #value <= maximum
end

local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if not text(a[field], 200) or a[field] ~= b[field] then
            return false
        end
    end
    return true
end

local function count(map, id)
    if type(map) ~= "table" then return nil end
    local value = map[id]
    if value == nil then value = 0 end
    if not integer(value, 0, 1000000000) then return nil end
    return value
end

local function listing(row)
    local origin = type(row) == "table" and row.itemOrigin
    if type(row) ~= "table" or not text(row.state, 40)
        or not text(row.item, 120)
        or not integer(row.indexed, 0, 1000000000)
        or not integer(row.price, 1, 9999999)
        or not integer(row.qty, 1, 999)
        or not integer(row.left, 0, row.qty)
        or not integer(row.createdAt, 0, 9007199254740991)
        or type(origin) ~= "table"
        or not integer(origin.total, 0, 1000000000)
        or not integer(origin.free, 0, origin.total) then
        return nil
    end
    return { state = row.state, item = row.item,
        indexed = row.indexed, price = row.price,
        qty = row.qty, left = row.left,
        createdAt = row.createdAt, total = origin.total,
        free = origin.free }
end

local function state(raw, itemId)
    local native = type(raw) == "table" and raw.native
    local market = type(native) == "table" and native.market
    local rows = type(market) == "table" and market.listings
    if type(native) ~= "table" or native.fullSync ~= true
        or type(rows) ~= "table" then return nil end
    local gold = count(native.inventory, "gold_bar")
    local boundGold = count(native.inventoryBound, "gold_bar")
    local item = count(native.inventory, itemId)
    local boundItem = count(native.inventoryBound, itemId)
    if gold == nil or boundGold == nil
        or item == nil or boundItem == nil then return nil end
    local listings, size = {}, 0
    for id, row in pairs(rows) do
        size = size + 1
        local saved = listing(row)
        if size > 100 or not text(id, 160)
            or not saved then return nil end
        listings[id] = saved
    end
    return { gold = gold, boundGold = boundGold,
        item = item, boundItem = boundItem,
        listings = listings, size = size }
end

local function sameListings(a, b)
    if a.size ~= b.size then return false end
    for id, row in pairs(a.listings) do
        local other = b.listings[id]
        if not other then return false end
        for _, field in ipairs({ "state", "item", "indexed",
            "price", "qty", "left", "createdAt", "total",
            "free" }) do
            if row[field] ~= other[field] then return false end
        end
    end
    return true
end

function MarketBuyEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if not same(proposal, before)
        or proposal.preflightOnly ~= true
        or proposal.feature ~= "marketFlip"
        or type(intent) ~= "table"
        or intent.kind ~= "marketBuy"
        or not (text(intent.listingId, 160)
            or integer(intent.listingId, 1, 9007199254740991))
        or not text(intent.itemId, 120)
        or intent.itemId == "gold_bar"
        or intent.quantity ~= 1
        or not integer(intent.quotedPrice, 1, 9999999)
        or type(before.native) ~= "table"
        or not finite(before.native.serverNow)
        or not integer(before.revision, 0, 9007199254740991)
        or proposal.revision ~= before.revision then
        return nil, "Market buy baseline mismatch"
    end
    local saved = state(before, intent.itemId)
    if not saved or saved.gold < intent.quotedPrice then
        return nil, "Market buy Gold baseline unavailable"
    end
    saved.session = proposal.session
    saved.account = proposal.account
    saved.place = proposal.place
    saved.release = proposal.release
    saved.revision = proposal.revision
    saved.itemId = intent.itemId
    saved.listingId = intent.listingId
    saved.price = intent.quotedPrice
    saved.serverNow = before.native.serverNow
    return saved, nil
end

-- Recovery observes custody only; ordinary broker confirmation still needs a reply.
function MarketBuyEvidence.observe(baseline, after)
    if type(baseline) ~= "table" or type(after) ~= "table"
        or not text(baseline.session, 200)
        or not text(after.session, 200)
        or not text(baseline.itemId, 120)
        or not integer(baseline.revision, 0, 9007199254740991)
        or not integer(after.revision, 0, 9007199254740991)
        or not finite(baseline.serverNow)
        or type(after.native) ~= "table"
        or not finite(after.native.serverNow)
        or after.native.serverNow < baseline.serverNow
        or not integer(baseline.price, 1, 9999999)
        or not integer(baseline.gold, baseline.price, 1000000000)
        or not integer(baseline.boundGold, 0, 1000000000)
        or not integer(baseline.item, 0, 1000000000)
        or not integer(baseline.boundItem, 0, 1000000000)
        or type(baseline.listings) ~= "table"
        or not integer(baseline.size, 0, 100) then return false end
    for _, field in ipairs({ "account", "place", "release" }) do
        if not text(baseline[field], 200)
            or baseline[field] ~= after[field] then return false end
    end
    local newer = baseline.session == after.session
        and after.revision > baseline.revision
        or baseline.session ~= after.session
            and after.native.serverNow > baseline.serverNow
    local current = state(after, baseline.itemId)
    return newer and current ~= nil
        and current.gold == baseline.gold - baseline.price
        and current.boundGold == baseline.boundGold
        and current.item == baseline.item + 1
        and current.boundItem == baseline.boundItem
        and sameListings(current, baseline)
end

local function reconcile(proposal, beforeHeader, after, reply, baseline, restart)
    local intent = type(proposal) == "table" and proposal.intent
    if not same(proposal, beforeHeader)
        or (not restart and not same(proposal, after))
        or type(after)~="table" or proposal.account~=after.account
        or proposal.place~=after.place or proposal.release~=after.release
        or not same(proposal, baseline)
        or type(reply) ~= "table"
        or type(intent) ~= "table"
        or intent.kind ~= "marketBuy"
        or intent.itemId ~= baseline.itemId
        or intent.listingId ~= baseline.listingId
        or intent.quotedPrice ~= baseline.price
        or proposal.revision ~= baseline.revision
        or beforeHeader.revision ~= baseline.revision then
        return "pending"
    end
    local current = state(after, baseline.itemId)
    if not current then return "pending" end
    local unchanged = current.gold == baseline.gold
        and current.boundGold == baseline.boundGold
        and current.item == baseline.item
        and current.boundItem == baseline.boundItem
        and sameListings(current, baseline)
    local advanced = MarketBuyEvidence.observe(baseline, after)
    if reply.pending==true or reply.code=="pending" or reply.code=="busy"
        or reply.code=="rate_limited" or reply.code=="presence" then return "pending" end
    if reply.ok == false then
        local newer=after.session==baseline.session and integer(after.revision,0,9007199254740991)
            and after.revision>baseline.revision
            or restart and after.session~=baseline.session and finite(after.native.serverNow)
                and after.native.serverNow>baseline.serverNow
        return newer and finite(after.native.serverNow) and after.native.serverNow>=baseline.serverNow
            and unchanged and "rejected" or "pending"
    end
    if reply.ok == true and reply.pending ~= true
        and reply.code ~= "rate_limited" and advanced then
        return "confirmed"
    end
    return "pending"
end

function MarketBuyEvidence.evaluate(proposal,beforeHeader,after,reply,baseline)
    return reconcile(proposal,beforeHeader,after,reply,baseline,false)
end
local function equal(a,b)
    if type(a)~=type(b) then return false end
    if type(a)~="table" then return a==b end
    for k,v in pairs(a) do if not equal(v,b[k]) then return false end end
    for k in pairs(b) do if a[k]==nil then return false end end
    return true
end
function MarketBuyEvidence.recoverSaved(data,after)
    if type(data)~="table" or type(data.proposal)~="table" or type(data.baseline)~="table"
        or type(data.reply)~="table" then return nil end
    local input={}
    for k,v in pairs(data.proposal) do input[k]=v end
    input.preflightOnly=true
    local expected=MarketBuyEvidence.capture(input,data.before)
    if not expected or not equal(expected,data.baseline) then return nil end
    local outcome=reconcile(input,data.before,after,data.reply,data.baseline,true)
    return (outcome=="confirmed" or outcome=="rejected") and outcome or nil
end
function MarketBuyEvidence.evaluateStored(baseline,after,reply)
    if type(baseline)~="table" then return "pending" end
    local p={feature="marketFlip",intent={kind="marketBuy",itemId=baseline.itemId,
        listingId=baseline.listingId,quotedPrice=baseline.price}}
    for _,key in ipairs({"session","account","place","release","revision"}) do p[key]=baseline[key] end
    return reconcile(p,p,after,reply,baseline,true)
end

return MarketBuyEvidence
