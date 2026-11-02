-- Read-only saved residency terms. Does not manufacture a lease or rollback.
local Residency = {}
local policies = {
    ["Income bonus"] = { landlord = true, jobCut = true, smugglers = true,
        operationSpeed = true, shopDiscount = true },
    ["Combat bonus"] = { enforcers = true, guardians = true, bosshunters = true,
        familyBoss = true, medics = true, runners = true },
}
local function number(value, low, high)
    return type(value) == "number" and value == value and value >= low and value <= high
end
local function integer(value, low, high)
    return number(value, low, high) and value % 1 == 0
end
local function text(value)
    return type(value) == "string" and #value > 0 and #value <= 120
end
function Residency.preview(raw, context, settings)
    local view = type(raw) == "table" and raw.residencyView
    if type(view) ~= "table" or type(view.header) ~= "table"
        or type(context) ~= "table" or type(raw.native) ~= "table"
        or raw.native.fullSync ~= true or not integer(raw.native.level, 1, 1000000)
        or type(settings) ~= "table" or not text(settings.districtId)
        or view.districtId ~= settings.districtId or not text(view.kind)
        or view.kind ~= settings.selectedKind
        or not integer(settings.maxRentPct, 0, 10)
        or not number(settings.minSharePct, 0, 100)
        or type(settings.allowReplace) ~= "boolean" or type(settings.allowRequests) ~= "boolean"
        or not ({ none = true, resident = true, pending = true })[view.status]
        or not ({ open = true, request = true, closed = true })[view.admission]
        or not number(view.rent, 0, 10) or not number(view.share, 0, 1)
        or not integer(view.count, 0, 500) or not integer(view.capacity, 1, 500)
        or view.count > view.capacity or not integer(view.minLevel, 0, 500)
        or (view.myRent ~= nil and not number(view.myRent, 0, 10))
        or (view.elsewhere ~= nil and not text(view.elsewhere)) then
        return nil, "Current residency terms, exact bonus kind and limits required"
    end
    for _, field in ipairs({ "session", "account", "place", "release", "revision", "capturedAt" }) do
        if raw[field] ~= context[field] or view.header[field] ~= context[field] then
            return nil, "Residency quote belongs to another Sync"
        end
    end
    local policy = settings.policy or "Selected bonus"
    if policy ~= "Selected bonus" and (not policies[policy] or not policies[policy][view.kind]) then
        return nil, "Selected resident bonus does not match the configured goal"
    end
    local rent = view.rent
    if (view.status == "resident" or view.status == "pending") and view.myRent ~= nil then
        rent = view.myRent
    end
    local reason
    if view.owned ~= true then reason = "Current district ownership required"
    elseif view.status == "resident" then reason = "Already resident"
    elseif view.status == "pending" then reason = "Owner approval pending"
    elseif view.admission == "closed" then reason = "Residency admission closed"
    elseif view.count >= view.capacity then reason = "Residency is full"
    elseif raw.native.level < view.minLevel then reason = "Residency level requirement unmet"
    elseif view.kind == "landlord" and rent / 100 >= view.share then reason = "Rent offsets the resident property-income bonus"
    elseif rent > settings.maxRentPct then reason = "Rent exceeds configured property-income percentage"
    elseif view.share * 100 < settings.minSharePct then reason = "Resident bonus is below configured minimum"
    elseif view.elsewhere and not settings.allowReplace then reason = "Replacing the previous lease is disabled"
    elseif view.admission == "request" and not settings.allowRequests then reason = "Owner-approved requests disabled" end
    return { readOnly = true, districtId = view.districtId, kind = view.kind,
        status = view.status, eligible = reason == nil, reason = reason,
        rentPct = rent, rentBasis = "property income", sharePct = view.share * 100,
        previousLeaseEnds = view.elsewhere ~= nil, previousResidence = view.elsewhere,
        requiresApproval = view.admission == "request", rollbackAvailable = false,
        effectiveGainVerified = false,
        effect = view.elsewhere and "Previous residency and bonus end when the move is accepted"
            or "Resident bonus starts when admission succeeds" }, nil
end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function leaseFrom(native)
    local lease = type(native) == "table" and type(native.derived) == "table" and native.derived.residency
    if lease == nil then return false end
    if type(lease) ~= "table" or not text(lease.d) or not number(lease.rent, 0, 10)
        or type(lease.active) ~= "boolean" then return nil end
    return {d = lease.d, rent = lease.rent, active = lease.active}
end
local headers = { "session", "account", "place", "release", "revision", "capturedAt" }
local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs(headers) do if a[field] ~= b[field] then return false end end
    return true
end
function Residency.read(raw, context)
    if not same(raw, context) or type(raw.native) ~= "table" or raw.native.fullSync ~= true
        or type(raw.native.derived) ~= "table" or type(raw.residencyView) ~= "table"
        or not same(raw.residencyView.header, context)
        or not integer(raw.revision, 0, 9007199254740991)
        or not number(raw.capturedAt, 0, 9007199254740991) then
        return nil, "Current native lease and snapshot-bound residency view required"
    end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(raw[field]) ~= "string" or #raw[field] == 0 or #raw[field] > 200 then
            return nil, "Invalid residency identity"
        end
    end
    local lease = raw.native.derived.residency
    if lease ~= nil and (type(lease) ~= "table" or not text(lease.d)) then
        return nil, "Native residency identity unavailable"
    end
    local result = { raw = raw, previousDistrict = lease and lease.d or "", lease = leaseFrom(raw.native),
        status = raw.residencyView.status }
    for _, field in ipairs(headers) do result[field] = raw[field] end
    if same(raw.residencyUsageProof, context)
        and integer(raw.residencyUsageProof.attempted, 0, 1000) then
        result.attempted = raw.residencyUsageProof.attempted
    end
    return result, nil
end
function Residency.propose(view, settings)
    if type(settings) ~= "table" or settings.enabled ~= true then return nil, "Residency selection disabled" end
    if type(view) ~= "table" or not integer(view.attempted, 0, 1000)
        or not integer(settings.maxAttempts, 0, 1000)
        or view.attempted >= settings.maxAttempts then return nil, "Owned residency attempt limit required" end
    local preview, reason = Residency.preview(view.raw, view.raw, settings)
    if not preview or not preview.eligible then return nil, reason or (preview and preview.reason) end
    if view.lease == nil or not number(view.raw.native.serverNow, 0, 9007199254740991) then
        return nil, "Current native lease cost and clock required"
    end
    if view.previousDistrict == preview.districtId then return nil, "Native lease already names this district" end
    if view.previousDistrict ~= "" and not settings.allowReplace then return nil, "Lease replacement disabled" end
    return { session = view.session, account = view.account, place = view.place,
        release = view.release, revision = view.revision, feature = "residency",
        actionKey = "residency:" .. preview.districtId .. ":" .. view.previousDistrict .. ":" .. view.attempted,
        resources = {}, intent = { kind = "residencyRequest", districtId = preview.districtId,
            previousDistrict = view.previousDistrict, rent = preview.rentPct,
            selectedKind = preview.kind, maxRentPct = settings.maxRentPct,
            minSharePct = settings.minSharePct, allowReplace = settings.allowReplace,
            allowRequests = settings.allowRequests, policy = settings.policy or "Selected bonus",
            maxAttempts = settings.maxAttempts, attemptedBefore = view.attempted } }, nil
end
function Residency.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    local view = Residency.read(before, before)
    if not view or type(intent) ~= "table" or proposal.feature ~= "residency"
        or intent.kind ~= "residencyRequest" or proposal.revision ~= before.revision then
        return nil, "Residency baseline changed"
    end
    local current = Residency.propose(view, { enabled = true, districtId = intent.districtId,
        selectedKind = intent.selectedKind, maxRentPct = intent.maxRentPct,
        minSharePct = intent.minSharePct, allowReplace = intent.allowReplace,
        allowRequests = intent.allowRequests, policy = intent.policy, maxAttempts = intent.maxAttempts })
    if not current or current.actionKey ~= proposal.actionKey or type(proposal.resources) ~= "table"
        or next(proposal.resources) ~= nil then return nil, "Residency admission or limits changed" end
    for field, value in pairs(current.intent) do
        if intent[field] ~= value then return nil, "Residency intent changed" end
    end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if proposal[field] ~= before[field] then return nil, "Residency account changed" end
    end
    local baseline = { intent = {}, status = view.status, revision = before.revision, lease = view.lease, serverNow = before.native.serverNow }
    for field, value in pairs(current.intent) do baseline.intent[field] = value end
    for _, field in ipairs({ "session", "account", "place", "release" }) do baseline[field] = before[field] end
    return baseline, nil
end
local function reconcile(proposal, before, after, reply, baseline, restart)
    if type(proposal) ~= "table" or type(baseline) ~= "table" or type(reply) ~= "table"
        or type(before) ~= "table" or proposal.feature ~= "residency" or type(proposal.intent) ~= "table"
        or type(baseline.intent) ~= "table" or not equal(proposal.intent, baseline.intent)
        or proposal.revision ~= baseline.revision or before.revision ~= baseline.revision
        or type(after) ~= "table" or type(after.native) ~= "table" or after.native.fullSync ~= true
        or not number(after.native.serverNow, baseline.serverNow, 9007199254740991)
        or not integer(after.revision, 0, 9007199254740991)
        or not (after.session == baseline.session and after.revision > baseline.revision
            or restart and after.session ~= baseline.session and after.native.serverNow > baseline.serverNow)
        or reply.code == "rate_limited" or reply.code == "presence" then return "pending" end
    for _, field in ipairs({"session", "account", "place", "release"}) do
        if proposal[field] ~= baseline[field] or before[field] ~= baseline[field]
            or (field ~= "session" or not restart) and after[field] ~= baseline[field] then return "pending" end
    end
    local lease = leaseFrom(after.native)
    if lease == nil then return "pending" end
    if reply.ok == false then
        return reply.pending ~= true and equal(lease, baseline.lease) and "rejected" or "pending"
    end
    local intent, quote = baseline.intent, after.residencyView
    if reply.ok ~= true or lease == false or lease.d ~= intent.districtId or lease.rent ~= intent.rent
        or lease.active ~= true then return "pending" end
    if quote ~= nil then
        if not same(quote.header, after) or quote.districtId ~= intent.districtId or quote.owned ~= true
            or quote.status ~= "resident" or quote.kind ~= intent.selectedKind
            or (quote.myRent or quote.rent) ~= intent.rent
            or not number(quote.share, intent.minSharePct / 100, 1) then return "pending" end
    end
    return "confirmed"
end
function Residency.evaluate(proposal, before, after, reply, baseline)
    return reconcile(proposal, before, after, reply, baseline, false)
end
function Residency.recoverSaved(data, after)
    if type(data) ~= "table" or type(data.reply) ~= "table" then return nil end
    local baseline = Residency.capture(data.proposal, data.before)
    if not baseline or not equal(baseline, data.baseline) then return nil end
    local outcome = reconcile(data.proposal, data.before, after, data.reply, baseline, true)
    return (outcome == "confirmed" or outcome == "rejected") and outcome or nil
end
function Residency.canDispatch(proposal, latest)
    if type(latest) ~= "table" or type(proposal.intent) ~= "table" then return false end
    local raw, proof = {}, {attempted = proposal.intent.attemptedBefore}
    for key, value in pairs(latest) do raw[key] = value end
    for _, field in ipairs(headers) do proof[field] = latest[field] end
    raw.residencyUsageProof = proof
    return Residency.capture(proposal, raw) ~= nil
end
return Residency
