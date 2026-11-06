-- EventShopTab buys one row by key. Opening/using the acquired item is a separate action.
-- Current attributes and durable sent-attempt/spend custody are injected by Task 24.
local EventShopBuyer = {}
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
local function identity(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0 or #a[field] > 200 or a[field] ~= b[field] then return false end
    end
    return true
end
local function inventory(raw)
    if type(raw) ~= "table" then return nil end
    local result, size = {}, 0
    for key, value in pairs(raw) do
        size = size + 1
        if size > 1000 or not id(key) or not integer(value, 0, 1000000000) then return nil end
        result[key] = value
    end
    return result
end
local function plan(view, settings)
    if type(settings) ~= "table" or settings.enabled ~= true then return nil, "Event Shop disabled" end
    if type(view) ~= "table" or not identity(view, view) or not integer(view.revision, 0, MAX)
        or not number(view.capturedAt, 0, MAX) or not integer(settings.medalReserve, 0, 1000000000)
        or not integer(settings.maxSpend, 0, 1000000000) or not integer(settings.maxAttempts, 0, 1000)
        or not inventory(view.inventory) or not inventory(view.inventoryBound)
        or type(view.sourceKey) ~= "string" or #view.sourceKey ~= 64 or not view.sourceKey:match("^[%x]+$")
        or not integer(view.sourceGeneration, 1, MAX) or type(view.restricted) ~= "boolean" then
        return nil, "Current Event Shop source, custody and valid limits required"
    end
    local row = type(view.offers) == "table" and view.offers[settings.offerKey]
    if type(row) ~= "table" or row.supported ~= true or not id(row.key) or row.key ~= settings.offerKey
        or not id(row.item) or row.item == "event_medal" or not integer(row.price, 1, 1000000000)
        or not integer(row.count, 1, 99) or (row.kind ~= "crate" and row.kind ~= "item")
        or type(view.inventory) ~= "table" or type(view.inventoryBound) ~= "table" then
        return nil, "Select a supported native Event Shop offer"
    end
    if view.open ~= true or not number(view.serverNow, 0, MAX) or not number(view.endsAt, 0, MAX)
        or (view.endsAt ~= 0 and view.serverNow >= view.endsAt) then return nil, "Native Event Shop window is closed" end
    if view.paidMedals ~= 0 then return nil, "Paid or mixed medal debit order is not established" end
    if not integer(view.attempted, 0, 1000) or not integer(view.spent, 0, 1000000000) then
        return nil, "Current durable Event Shop usage proof required"
    end
    if view.attempted >= settings.maxAttempts then return nil, "Event Shop attempt cap reached" end
    if view.spent + row.price > settings.maxSpend then return nil, "Event Shop medal spend cap reached" end
    if not integer(view.medals, 0, 1000000000) or view.medals - row.price < settings.medalReserve then
        return nil, "Event Shop medal reserve or balance insufficient"
    end
    return { session = view.session, account = view.account, place = view.place, release = view.release,
        revision = view.revision, feature = "eventShop", actionKey = "event-shop:" .. row.key .. ":" .. view.attempted,
        resources = { event_medal = row.price }, intent = { kind = "eventShopBuy", offerKey = row.key,
            item = row.item, itemCount = row.count, rowKind = row.kind, price = row.price,
            quantity = 1, currency = "medal", sourceKey = view.sourceKey, sourceGeneration = view.sourceGeneration,
            medalsBefore = view.medals, attemptedBefore = view.attempted, spentBefore = view.spent,
            itemLooseBefore = view.inventory[row.item] or 0, itemBoundBefore = view.inventoryBound[row.item] or 0,
            medalReserve = settings.medalReserve, maxSpend = settings.maxSpend,
            maxAttempts = settings.maxAttempts, endsAt = view.endsAt, restricted = view.restricted } }, nil
end
function EventShopBuyer.new(source)
    assert(type(source) == "table" and type(source.Read) == "function", "Current native Event Shop source required")
    local result = {}
    result.read = function(raw, context, saved)
        local proof, reason
        if saved then
            if type(source.ReadSaved) ~= "function" then return nil, "Saved Event source unavailable" end
            proof, reason = source:ReadSaved(raw, context)
        else proof, reason = source:Read(raw, context) end
        if not proof then return nil, reason end
        local loose, bound = inventory(raw.native.inventory), inventory(raw.native.inventoryBound)
        local paid = raw.native.paidMedals
        if paid == nil then paid = 0 end -- Native EventShop.paidMedals treats an absent marker as zero.
        if not loose or not bound or not integer(paid, 0, 1000000000) then return nil, "Complete native medal/item custody required" end
        local view = copy(proof.header)
        for _, field in ipairs({ "offers", "sourceKey", "sourceGeneration", "open", "endsAt", "serverNow", "restricted" }) do view[field] = proof[field] end
        view.inventory, view.inventoryBound, view.paidMedals = loose, bound, paid
        view.medals = bound.event_medal or 0
        local usage = raw.eventShopUsageProof
        local matched = type(usage) == "table"
        for _, field in ipairs(fields) do if not matched or usage[field] ~= raw[field] then matched = false; break end end
        if matched and integer(usage.attempted, 0, 1000) and integer(usage.spent, 0, 1000000000) then
            view.attempted, view.spent = usage.attempted, usage.spent
        end
        return view, nil
    end
    result.propose = plan
    result.capture = function(proposal, before, saved)
        local intent = type(proposal) == "table" and proposal.intent
        local view = result.read(before, before, saved)
        if not view or type(intent) ~= "table" or not identity(proposal, view) or proposal.revision ~= view.revision
            or proposal.feature ~= "eventShop" then return nil, "Event Shop baseline identity changed" end
        local expected = plan(view, { enabled = true, offerKey = intent.offerKey, medalReserve = intent.medalReserve,
            maxSpend = intent.maxSpend, maxAttempts = intent.maxAttempts })
        if not expected or expected.actionKey ~= proposal.actionKey or not same(expected.intent, intent)
            or not same(expected.resources, proposal.resources) then return nil, "Event Shop source, custody, usage or limits changed" end
        local baseline = copy(view)
        baseline.actionKey, baseline.intent = proposal.actionKey, copy(intent)
        return baseline, nil
    end
    local function reconcile(proposal, before, after, reply, baseline, restart)
        if type(proposal) ~= "table" or type(baseline) ~= "table" or type(baseline.intent) ~= "table"
            or not inventory(baseline.inventory) or not inventory(baseline.inventoryBound) or type(reply) ~= "table"
            or not integer(baseline.revision, 0, MAX) or not number(baseline.serverNow, 0, MAX)
            or not number(baseline.capturedAt, 0, MAX) or not id(baseline.intent.item)
            or not integer(baseline.intent.itemCount, 1, 99) or not integer(baseline.intent.price, 1, 1000000000)
            or not identity(proposal, baseline) or not identity(before, baseline) or type(after) ~= "table"
            or after.account ~= baseline.account or after.place ~= baseline.place or after.release ~= baseline.release
            or not restart and after.session ~= baseline.session
            or reply.pending == true or reply.code == "rate_limited" or reply.code == "presence"
            or proposal.feature ~= "eventShop" or proposal.actionKey ~= baseline.actionKey
            or proposal.revision ~= baseline.revision or not same(proposal.intent, baseline.intent)
            or not same(proposal.resources, { event_medal = baseline.intent.price }) then return "pending" end
        for _, field in ipairs(fields) do if before[field] ~= baseline[field] then return "pending" end end
        local current
        if restart then
            local native = after.native
            if type(native) ~= "table" or native.fullSync ~= true then return "pending" end
            local loose, bound = inventory(native.inventory), inventory(native.inventoryBound)
            local paid = native.paidMedals
            if paid == nil then paid = 0 end
            if not loose or not bound or not integer(paid, 0, 1000000000) then return "pending" end
            current = {inventory = loose, inventoryBound = bound, paidMedals = paid,
                revision = after.revision, serverNow = native.serverNow, capturedAt = after.capturedAt,
                sourceKey = source.sourceKey, offers = baseline.offers}
        else current = result.read(after, after) end
        if not current or current.sourceKey ~= baseline.sourceKey or current.paidMedals ~= 0
            or not integer(current.revision, 0, MAX) or not number(current.serverNow, baseline.serverNow, MAX)
            or not number(current.capturedAt, 0, MAX)
            or not (after.session == baseline.session and current.revision > baseline.revision
                or restart and after.session ~= baseline.session and current.serverNow > baseline.serverNow)
            or not restart and current.capturedAt < baseline.capturedAt then return "pending" end
        local intent = baseline.intent
        if reply.ok == false then
            return same(current.inventory, baseline.inventory) and same(current.inventoryBound, baseline.inventoryBound)
                and "rejected" or "pending"
        end
        if reply.ok ~= true or reply.pending == true or reply.code == "rate_limited" then return "pending" end
        if not same(current.offers, baseline.offers) then return "pending" end
        local function delta(map, old, key) return (map[key] or 0) - (old[key] or 0) end
        if delta(current.inventoryBound, baseline.inventoryBound, "event_medal") ~= -intent.price
            or delta(current.inventory, baseline.inventory, "event_medal") ~= 0 then return "pending" end
        local loose = delta(current.inventory, baseline.inventory, intent.item)
        local bound = delta(current.inventoryBound, baseline.inventoryBound, intent.item)
        if loose < 0 or bound < 0 or loose + bound ~= intent.itemCount then return "pending" end
        for _, maps in ipairs({ { current.inventory, baseline.inventory }, { current.inventoryBound, baseline.inventoryBound } }) do
            for _, map in ipairs(maps) do
                for key in pairs(map) do
                    if key ~= intent.item and key ~= "event_medal" and delta(maps[1], maps[2], key) ~= 0 then return "pending" end
                end
            end
        end
        return "confirmed"
    end
    result.evaluate = function(proposal, before, after, reply, baseline)
        return reconcile(proposal, before, after, reply, baseline, false)
    end
    result.recoverSaved = function(data, after)
        if type(data) ~= "table" or type(data.reply) ~= "table" then return nil end
        local baseline = result.capture(data.proposal, data.before, true)
        if not baseline or not same(baseline, data.baseline) then return nil end
        local outcome = reconcile(data.proposal, data.before, after, data.reply, baseline, true)
        return (outcome == "confirmed" or outcome == "rejected") and outcome or nil
    end
    return result
end
function EventShopBuyer.describe(proposal)
    local intent = type(proposal) == "table" and proposal.intent
    if type(intent) ~= "table" or proposal.feature ~= "eventShop" or intent.kind ~= "eventShopBuy"
        or not id(intent.offerKey) or not id(intent.item) or intent.item == "event_medal"
        or (intent.rowKind ~= "item" and intent.rowKind ~= "crate") or intent.quantity ~= 1 or intent.currency ~= "medal"
        or not integer(intent.itemCount, 1, 99) or not integer(intent.price, 1, 1000000000)
        or not integer(intent.itemLooseBefore, 0, 1000000000) or not integer(intent.itemBoundBefore, 0, 1000000000)
        or not integer(intent.medalReserve, 0, 1000000000) or not integer(intent.medalsBefore, intent.price + intent.medalReserve, 1000000000)
        or not integer(intent.maxAttempts, 1, 1000) or not integer(intent.attemptedBefore, 0, intent.maxAttempts - 1)
        or not integer(intent.maxSpend, 1, 1000000000) or not integer(intent.spentBefore, 0, intent.maxSpend - intent.price)
        or type(intent.sourceKey) ~= "string" or #intent.sourceKey ~= 64 or not intent.sourceKey:match("^[%x]+$")
        or not integer(intent.sourceGeneration, 1, MAX) or not number(intent.endsAt, 0, MAX)
        or type(intent.restricted) ~= "boolean" or not same(proposal.resources, { event_medal = intent.price }) then
        return nil, "Reviewed single Event Shop acquisition and explicit budget required"
    end
    local allowed = { kind = true, offerKey = true, item = true, itemCount = true, rowKind = true, price = true,
        quantity = true, currency = true, sourceKey = true, sourceGeneration = true, medalsBefore = true, attemptedBefore = true,
        spentBefore = true, itemLooseBefore = true, itemBoundBefore = true, medalReserve = true,
        maxSpend = true, maxAttempts = true, endsAt = true, restricted = true }
    for field in pairs(intent) do if not allowed[field] then return nil, "Unknown Event Shop buy intent field" end end
    return { remote = "EventShopAction", method = "InvokeServer", arity = 4,
        args = { "buy", intent.offerKey, 1, "medal" }, source = "current EventShopTab earned-Medal single offer purchase" }, nil
end
return EventShopBuyer
