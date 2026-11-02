-- One-period rental planning from tab-owned terms and checkpoint-owned exposure.
local Runtime = {}
local headers = {"session", "account", "place", "release", "revision", "capturedAt"}
local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs(headers) do if a[field] ~= b[field] then return false end end
    return true
end
local function equal(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return a == b end
    for key, value in pairs(a) do if b[key] ~= value then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function terms(raw)
    local proof = type(raw) == "table" and raw.marketRentTermsProof
    local value = type(proof) == "table" and proof.terms
    if not same(proof, raw) or type(value) ~= "table" or value.release ~= raw.release
        or type(value.sourceKey) ~= "string" or #value.sourceKey ~= 64
        or not value.sourceKey:match("^[%x]+$") then return nil end
    return value
end
function Runtime.new(deps)
    assert(type(deps) == "table" and type(deps.MarketRentQuote) == "table"
        and type(deps.MarketRentEvidence) == "table" and type(deps.MarketSettings) == "table", "Rental modules unavailable")
    local result = {}
    function result.read(raw, context)
        local current = terms(raw)
        local usage = type(raw) == "table" and raw.marketRentUsageProof
        if not same(raw, context) or not current or not same(usage, raw) then return nil, "Owned rental terms and allowance required" end
        return {raw = raw, context = context, terms = current, usage = usage}, nil
    end
    function result.propose(view, settings)
        if type(view) ~= "table" or type(settings) ~= "table" then return nil, "Rental input unavailable" end
        local custom = type(settings.custom) == "table" and settings.custom or settings
        local preferences = {enabled = settings.enabled, goldReserve = custom.goldReserve,
            maxAttempts = custom.maxAttempts, maxGoldSpend = custom.maxGoldSpend}
        local projected, reason = deps.MarketSettings.project("marketRent", preferences,
            {spent = view.usage.spent, attempted = view.usage.attempted})
        if not projected then return nil, reason end
        local proposal, why = deps.MarketRentQuote.assess(view.raw, view.context, view.terms, projected.rent, projected.attempted)
        if not proposal then return nil, why end
        proposal.actionKey = "market-rent:" .. view.terms.sourceKey .. ":" .. view.usage.attempted .. ":" .. view.raw.native.market.shopUntil
        proposal.resources = {gold_bar = proposal.intent.cost}
        local intent = proposal.intent
        intent.attemptedBefore, intent.spentBefore = view.usage.attempted, view.usage.spent
        intent.maxAttempts, intent.maxGoldSpend = preferences.maxAttempts, preferences.maxGoldSpend
        intent.goldReserve, intent.sourceKey = preferences.goldReserve, view.terms.sourceKey
        return proposal, nil
    end
    function result.capture(proposal, before)
        if type(proposal) ~= "table" or type(proposal.intent) ~= "table" then return nil, "Rental intent missing" end
        local context = {}
        for _, field in ipairs(headers) do context[field] = field == "capturedAt" and before.capturedAt or proposal[field] end
        local view = result.read(before, context)
        if not view then return nil, "Rental source changed" end
        local intent = proposal.intent
        local planned = result.propose(view, {enabled = true, custom = {goldReserve = intent.goldReserve,
            maxAttempts = intent.maxAttempts, maxGoldSpend = intent.maxGoldSpend}})
        if not planned or planned.actionKey ~= proposal.actionKey or not equal(planned.intent, intent)
            or not equal(planned.resources, proposal.resources) then return nil, "Rental quote or allowance changed" end
        return deps.MarketRentEvidence.capture(proposal, before)
    end
    result.evaluate = deps.MarketRentEvidence.evaluate
    function result.recoverSaved(data, after)
        if type(data) ~= "table" or type(data.baseline) ~= "table" then return nil end
        local expected = result.capture(data.proposal, data.before)
        local current = terms(after)
        if not expected or not equal(expected, data.baseline) or not current
            or current.sourceKey ~= data.proposal.intent.sourceKey
            or current.rentPerPeriod ~= data.proposal.intent.cost
            or current.rentPeriodHours * 3600 ~= data.proposal.intent.durationSeconds then return nil end
        return deps.MarketRentEvidence.recoverSaved(data, after)
    end
    return result
end
return Runtime
