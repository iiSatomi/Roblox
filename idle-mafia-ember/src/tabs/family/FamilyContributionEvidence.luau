-- Personal counter receipt plus exact newer own-resource debit.
local FamilyContributionEvidence = {}
local features = { familyCash = "cash", familyGold = "gold_bar", familyStamina = "stamina" }

local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0 or a[field] ~= b[field] then return false end
    end
    return true
end

local function balance(raw, resource)
    local native = type(raw) == "table" and raw.native
    if type(native) ~= "table" or native.fullSync ~= true then return nil end
    local value
    if resource == "cash" then value = native.cash
    elseif resource == "stamina" and type(native.pools) == "table" then value = native.pools.stamina
    elseif resource == "gold_bar" and type(native.inventory) == "table"
        and type(native.inventoryBound) == "table" then
        local bound = native.inventoryBound.gold_bar
        if bound == nil then bound = 0 end
        if bound ~= 0 then return nil end
        value = native.inventory.gold_bar
        if value == nil then value = 0 end
    end
    if type(value) == "number" and value == value and value >= 0
        and value <= 9007199254740991 then return value end
    return nil
end

function FamilyContributionEvidence.new(state)
    assert(type(state) == "table" and type(state.read) == "function"
        and type(state.parseFamily) == "function", "Missing Family contribution reader")
    local evidence = {}
    function evidence.capture(proposal, before)
        local intent = type(proposal) == "table" and proposal.intent
        local view = state.read(before, before)
        if not same(proposal, before) or not view or type(intent) ~= "table"
            or intent.kind ~= "familyContribution" or features[proposal.feature] ~= intent.resource
            or proposal.revision ~= before.revision or intent.actorId ~= view.actorId
            or (intent.actorAccount ~= nil and intent.actorAccount ~= before.account)
            or intent.familyId ~= view.familyId or intent.ledgerBefore ~= view.ledger[intent.resource]
            or type(intent.amount) ~= "number" or intent.amount % 1 ~= 0 or intent.amount < 1
            or intent.amount > 1000000000000000 then return nil, "Personal Family baseline changed" end
        local usage = type(view.usage) == "table" and view.usage[proposal.feature]
        if type(usage) ~= "table" or usage.spent ~= intent.spentBefore
            or usage.attempted ~= intent.attemptsBefore
            or type(intent.reserve) ~= "number" or intent.reserve < 0 or intent.reserve % 1 ~= 0
            or type(intent.runBudget) ~= "number" or intent.runBudget % 1 ~= 0
            or intent.runBudget < usage.spent + intent.amount
            or type(intent.maxAttempts) ~= "number" or intent.maxAttempts % 1 ~= 0
            or intent.maxAttempts <= usage.attempted
            or type(proposal.resources) ~= "table"
            or proposal.resources[intent.resource] ~= intent.amount then
            return nil, "Family run limits or resource exposure changed"
        end
        local resourceCount = 0
        for _ in pairs(proposal.resources) do resourceCount = resourceCount + 1 end
        if resourceCount ~= 1 then return nil, "Unexpected Family resource exposure" end
        local current = balance(before, intent.resource)
        if not current or current - intent.amount < intent.reserve then
            return nil, "Family resource baseline missing"
        end
        if intent.resource == "stamina" and (type(intent.perkLevelBefore) ~= "number"
            or intent.perkLevelBefore % 1 ~= 0 or intent.perkLevelBefore < 0
            or intent.perkLevelBefore > 24 or type(intent.perkId) ~= "string"
            or type(intent.perkProgressBefore) ~= "number" or type(intent.perkCost) ~= "number"
            or view.perks[intent.perkId] ~= intent.perkLevelBefore
            or view.progress[intent.perkId] ~= intent.perkProgressBefore
            or view.staminaCosts[intent.perkLevelBefore + 1] ~= intent.perkCost
            or intent.amount + intent.perkProgressBefore > intent.perkCost) then
            return nil, "Family perk quote changed"
        end
        local baseline = { revision = before.revision, balance = current,
            familyId = intent.familyId, actorId = intent.actorId, resource = intent.resource,
            amount = intent.amount, ledger = intent.ledgerBefore, perkId = intent.perkId,
            perkLevel = intent.perkLevelBefore, progress = intent.perkProgressBefore,
            cost = intent.perkCost, serverNow = before.native.serverNow,
            sourceKey = before.familyContributionCatalog.key, nativeActor = before.native.userId }
        for _, key in ipairs({ "session", "account", "place", "release" }) do baseline[key] = before[key] end
        return baseline, nil
    end
    local function reconcile(proposal, before, after, reply, baseline, restart)
        local intent = type(proposal) == "table" and proposal.intent
        if not same(proposal, before) or type(after) ~= "table" or not same(proposal, baseline)
            or proposal.account ~= after.account or proposal.place ~= after.place or proposal.release ~= after.release
            or (not restart and not same(proposal, after))
            or type(intent) ~= "table" or intent.kind ~= "familyContribution"
            or features[proposal.feature] ~= baseline.resource
            or intent.resource ~= baseline.resource or intent.amount ~= baseline.amount
            or intent.ledgerBefore ~= baseline.ledger or intent.actorId ~= baseline.actorId
            or intent.perkId ~= baseline.perkId or intent.perkLevelBefore ~= baseline.perkLevel
            or intent.perkProgressBefore ~= baseline.progress or intent.perkCost ~= baseline.cost
            or intent.familyId ~= baseline.familyId or proposal.revision ~= baseline.revision
            or before.revision ~= baseline.revision or type(reply) ~= "table"
            or (intent.actorAccount ~= nil and intent.actorAccount ~= baseline.account)
            or type(after.native) ~= "table" or type(after.native.family) ~= "table"
            or ((baseline.nativeActor ~= nil or after.native.userId ~= nil)
                and after.native.userId ~= baseline.actorId)
            or after.native.family.id ~= baseline.familyId
            or type(after.revision) ~= "number" or after.revision % 1 ~= 0 or after.revision < 0
            or type(baseline.serverNow) ~= "number" or baseline.serverNow < 0 or baseline.serverNow == math.huge
            or type(after.native.serverNow) ~= "number" or after.native.serverNow ~= after.native.serverNow
            or after.native.serverNow < baseline.serverNow or after.native.serverNow == math.huge
            or not (after.session == baseline.session and after.revision > baseline.revision
                or restart and after.session ~= baseline.session and after.native.serverNow > baseline.serverNow)
            or type(after.familyContributionCatalog) ~= "table"
            or after.familyContributionCatalog.key ~= baseline.sourceKey
            or reply.pending == true or reply.code == "rate_limited" or reply.code == "presence" then return "pending" end
        local current = balance(after, baseline.resource)
        if not current then return "pending" end
        if reply.ok == false then
            local receipt = reply.family ~= nil and state.parseFamily(reply.family, baseline.actorId)
            if reply.family ~= nil and (not receipt or receipt.familyId ~= baseline.familyId
                or receipt.ledger[baseline.resource] ~= baseline.ledger) then return "pending" end
            return current == baseline.balance and "rejected" or "pending"
        end
        if reply.ok ~= true or reply.pending == true or reply.code == "rate_limited"
            or current ~= baseline.balance - baseline.amount then
            return "pending"
        end
        local receipt = state.parseFamily(reply.family, baseline.actorId)
        if not receipt or receipt.familyId ~= baseline.familyId
            or receipt.ledger[baseline.resource] ~= baseline.ledger + baseline.amount then return "pending" end
        if baseline.resource == "stamina" then
            local progress, level = baseline.progress + baseline.amount, baseline.perkLevel
            if progress == baseline.cost then progress, level = 0, level + 1 end
            if (receipt.perks[baseline.perkId] or 0) ~= level
                or (receipt.progress[baseline.perkId] or 0) ~= progress then return "pending" end
        end
        return "confirmed"
    end
    function evidence.evaluate(proposal, before, after, reply, baseline)
        return reconcile(proposal, before, after, reply, baseline, false)
    end
    local function equal(a, b)
        if type(a) ~= type(b) then return false end
        if type(a) ~= "table" then return a == b end
        for k, v in pairs(a) do if not equal(v, b[k]) then return false end end
        for k in pairs(b) do if a[k] == nil then return false end end
        return true
    end
    function evidence.recoverSaved(data, after)
        if type(data) ~= "table" or type(data.reply) ~= "table" then return nil end
        local baseline = evidence.capture(data.proposal, data.before)
        if not baseline or not equal(baseline, data.baseline) then return nil end
        local result = reconcile(data.proposal, data.before, after, data.reply, baseline, true)
        return (result == "confirmed" or result == "rejected") and result or nil
    end
    function evidence.canDispatch(proposal, snapshot)
        local intent = type(proposal) == "table" and proposal.intent
        if type(snapshot) ~= "table" or type(intent) ~= "table" then return false end
        local before, proof = {}, {usage = {}}
        for key, value in pairs(snapshot) do before[key] = value end
        for _, key in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do proof[key] = snapshot[key] end
        -- Only the admitted feature's original counters are read by capture;
        -- Checkpoint already persisted its charge before this native recheck.
        for feature in pairs(features) do proof.usage[feature] = {attempted = 0, spent = 0} end
        proof.usage[proposal.feature] = {attempted = intent.attemptsBefore, spent = intent.spentBefore}
        before.familyUsageProof = proof
        return evidence.capture(proposal, before) ~= nil
    end
    return evidence
end

return FamilyContributionEvidence
