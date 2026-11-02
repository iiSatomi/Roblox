-- Tab-owned lifecycle for one ordinary funded dismissal/hire cycle.
local CrewReplacementRuntime = {}
local fields = {"session", "account", "place", "release", "revision", "capturedAt"}
local function stamp(raw)
    local result = {}
    for _, key in ipairs(fields) do result[key] = raw[key] end
    return result
end
function CrewReplacementRuntime.new(deps)
    if type(deps) ~= "table" or type(deps.identity) ~= "table" or type(deps.clock) ~= "table"
        or type(deps.clock.Now) ~= "function" or type(deps.helper) ~= "table"
        or type(deps.transactions) ~= "table" or type(deps.transactions.new) ~= "function" then
        return nil, "Crew replacement runtime dependencies unavailable"
    end
    local scope = {account = deps.identity.account, place = deps.identity.place,
        release = deps.identity.release, ownerId = "crew-replacement-v1"}
    local owner, reason = deps.transactions.new(deps.storage, scope, deps.helper)
    if not owner then return nil, reason end
    local helper, closed, seen = deps.helper, false, nil
    local result = {owner = owner}
    local function sameProposal(a, b)
        if type(a) ~= "table" or type(b) ~= "table" then return false end
        for _, key in ipairs({"session", "account", "place", "release", "revision", "feature", "actionKey"}) do
            if a[key] ~= b[key] then return false end
        end
        return helper.Same(a.intent, b.intent) and helper.Same(a.resources, b.resources)
    end
    function result:Enrich(raw, settings)
        local enriched = {}
        for key, value in pairs(raw) do enriched[key] = value end
        enriched.crewReplacementOwnerProof, enriched.crewReplacementUsageProof = nil, nil
        if closed or type(raw.native) ~= "table" or raw.native.fullSync ~= true then return enriched end
        for _, key in ipairs({"session", "account", "place", "release"}) do
            if raw[key] ~= deps.identity[key] then return enriched end
        end
        local usage = owner:Usage()
        if not usage then return enriched end
        local active = owner:Active()
        local choices = type(settings) == "table" and settings.crewRoll
        choices = type(choices) == "table" and (choices.custom or choices) or {}
        local slot = active and active.funded.slot or choices.slot or 2
        local proof = stamp(raw)
        proof.ownerId, proof.slot = scope.ownerId, slot
        enriched.crewReplacementOwnerProof = proof
        proof = stamp(raw)
        proof.attempted, proof.spent, proof.controllersClear = usage.attempted, usage.spent, true
        if active and active.stage == "preparedDismiss" then
            -- Recheck the exact reserved cycle against its original allowance.
            -- Stored usage already counts it; no new cycle can use these totals.
            proof.attempted, proof.spent = active.funded.attemptedBefore, active.funded.spentBefore
        end
        enriched.crewReplacementUsageProof = proof
        local key = tostring(raw.session) .. ":" .. tostring(raw.revision) .. ":" .. tostring(raw.capturedAt)
        if active and (active.stage == "sentDismiss" or active.stage == "sentHire") and seen ~= key then
            seen = key
            owner:Reconcile(enriched, deps.clock:Now())
        end
        return enriched
    end
    result.lifecycle = {
        prepare = function(proposal, before, _, now)
            if closed or owner.fault then return false, owner.fault or "Crew runtime closed" end
            local active = owner:Active()
            if not active then return owner:PrepareDismiss(proposal, before, now) end
            if active.stage == "observedEmpty" then
                local nextProposal, why = owner:PrepareHire(before, now)
                if not nextProposal then return false, why end
                active = owner:Active()
            end
            if not owner:IsPreparedHere() or not sameProposal(active.proposal, proposal) then
                return false, "Crew stage is not this exact live preparation"
            end
            return true
        end,
        authorize = function(proposal, before, now)
            local active = owner:Active()
            if closed or not active or not sameProposal(active.proposal, proposal) then return nil, "Crew stage changed" end
            local saved, why = owner:MarkSending(before, now)
            if not saved then return nil, why end
            return owner:SubmitCall(before, now)
        end,
        returned = function(proposal, reply)
            if closed then return false, "Crew runtime closed" end
            return owner:AcceptReply(proposal.actionKey, reply)
        end,
        resolve = function(proposal, outcome, after, now)
            if closed then return false, "Crew runtime closed" end
            local active = owner:Active()
            if not active or not sameProposal(active.proposal, proposal) then return false, "Crew outcome owner changed" end
            if outcome == "confirmed" then
                if active.stage == "sentDismiss" or active.stage == "sentHire" then
                    local saved, why = owner:Reconcile(after, now)
                    if not saved then return false, why end
                    active = owner:Active()
                end
                if active.stage == "observedMember" then return owner:ClearObserved() end
                return active.stage == "observedEmpty"
            end
            if outcome == "rejected" and helper.reconcile(active.proposal, active.baseline, after, active.reply, true) == "rejected" then
                -- Rejected hire keeps the funded empty slot and conservative exposure.
                -- No implicit retry or discard of that intermediate custody.
                if active.stage == "sentDismiss" then return owner:save(nil) end
                return true
            end
            return false, "Crew outcome remains unconfirmed"
        end,
        unsent = function(proposal)
            if closed then return false, "Crew runtime closed" end
            local active = owner:Active()
            if active and active.stage == "observedEmpty" and proposal.intent.kind == "crewReplacementHire" then return true end
            return owner:CancelUnsent(proposal.actionKey)
        end,
        abandonedUnsent = function(proposal)
            -- Called only after the adapter proves it never entered invocation.
            -- It cannot rewrite the transaction or generic checkpoint of a new owner.
            return owner:RecordAbandonedUnsent(proposal.actionKey)
        end,
    }
    result.lifecycle.recover = function(data, after, now)
        if closed or type(data) ~= "table" or type(data.proposal) ~= "table"
            or data.proposal.feature ~= "crewRoll" or type(data.proposal.intent) ~= "table"
            or data.proposal.intent.ownerId ~= scope.ownerId or data.proposal.intent.sourceKey ~= helper.key
            or not helper.ValidBaseline(data.proposal, data.baseline) then return nil end
        local receipt = owner:Resolution()
        if receipt and receipt.kind == "known_unsent" and data.reply == nil
            and sameProposal(receipt.proposal, data.proposal) and helper.Same(receipt.baseline, data.baseline) then
            return "known_unsent"
        end
        local outcome = helper.reconcile(data.proposal, data.baseline, after, data.reply, true)
        if outcome ~= "confirmed" and outcome ~= "rejected" then return nil end
        local active, usage = owner:Active(), owner:Usage()
        local intent = data.proposal.intent
        if not usage or usage.attempted ~= intent.attemptedBefore + 1 then return nil end
        if active then
            if not sameProposal(active.proposal, data.proposal) or not helper.Same(active.baseline, data.baseline)
                or helper.reconcile(active.proposal, active.baseline, after, active.reply, true) ~= outcome then return nil end
            local saved = result.lifecycle.resolve(data.proposal, outcome, after, now)
            return saved == true and outcome or nil
        end
        -- A crash can fall between clearing a terminal transaction and clearing
        -- its generic checkpoint. Exact effects plus its durable cycle totals
        -- recover that window without resubmitting any request.
        local terminalHire = outcome == "confirmed" and intent.kind == "crewReplacementHire"
            and usage.spent == intent.spentBefore + intent.cost
        local terminalDismiss = outcome == "rejected" and intent.kind == "crewReplacementDismiss"
            and usage.spent == intent.spentBefore
        local reviewedHire = outcome == "rejected" and receipt and receipt.kind == "rejected"
            and sameProposal(receipt.proposal, data.proposal) and helper.Same(receipt.baseline, data.baseline)
            and helper.reconcile(receipt.proposal, receipt.baseline, after, receipt.reply, true) == "rejected"
        return (terminalHire or terminalDismiss or reviewedHire) and outcome or nil
    end
    if type(deps.review) == "table" and type(deps.review.new) == "function" then
        result.lifecycle.recoveryFactory = function(environment)
            return deps.review.new({owner = owner, helper = helper, environment = environment})
        end
    end
    function result:Close() closed = true; owner:Close() end
    return result, nil
end
return CrewReplacementRuntime
