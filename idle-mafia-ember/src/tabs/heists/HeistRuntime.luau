-- One native queue and durable lifecycle shared by all four ordinary Heist controls.
local Runtime = {}
local headers = {"session", "account", "place", "release", "revision", "capturedAt"}
local function copy(value) local out = {}; for key, part in pairs(value) do out[key] = part end; return out end
local function same(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not same(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function matched(proposal, data)
    if type(proposal) ~= "table" or type(data) ~= "table" or type(data.proposal) ~= "table" then return false end
    for _, field in ipairs({"session", "account", "place", "release", "revision", "feature", "actionKey"}) do
        if proposal[field] ~= data.proposal[field] then return false end
    end
    return same(proposal.intent, data.proposal.intent) and same(proposal.resources, data.proposal.resources)
end
function Runtime.new(deps)
    local source = type(deps) == "table" and deps.nativeHeistController
    if type(source) ~= "table" or type(deps.HeistTransactions) ~= "table"
        or type(deps.HeistCollection) ~= "table" or type(deps.HeistCollection.new) ~= "function"
        or type(deps.SequenceRecovery) ~= "table" then return nil, "Native Heist lifecycle unavailable" end
    local methods = {}
    for _, field in ipairs({"Read", "Current", "Start", "Busy", "Release"}) do
        if type(source[field]) ~= "function" then return nil, "Current native Heist methods required" end
        methods[field] = source[field]
    end
    local collection = deps.HeistCollection.new(deps.sha256, deps.fingerprint, deps.release)
    local evidence = {heists = deps.HeistStartEvidence, heistCollect = collection,
        favors = deps.FavorHelpEvidence, sabotage = deps.SabotageEvidence}
    local owner, why = deps.HeistTransactions.new(deps.storage, deps.identity,
        deps.PendingAction, deps.HeistCallPlan, evidence)
    if not owner then return nil, why end
    local closed, latest, accounting, accountingMethods = false, nil, nil, nil
    local result = {owner = owner, collection = collection}
    function result:BindAccounting(checkpoint)
        if closed or type(checkpoint) ~= "table" or accounting and accounting ~= checkpoint then return false end
        local captured = {}
        for _, field in ipairs({"FavorUsage", "SabotageUsage", "Recovery"}) do
            if type(checkpoint[field]) ~= "function" or accountingMethods and accountingMethods[field] ~= checkpoint[field] then return false end
            captured[field] = checkpoint[field]
        end
        accounting, accountingMethods = checkpoint, captured
        return true
    end
    local function native()
        if closed or owner.fault then return nil end
        for field, method in pairs(methods) do if source[field] ~= method then return nil end end
        local ok, current = pcall(methods.Current)
        if not ok or current ~= true then return nil end
        local readOk, value = pcall(methods.Read)
        return readOk and type(value) == "table" and value or nil
    end
    local function activeFor(proposal)
        local active = owner:Active()
        return active and matched(proposal, active.recovery) and active or nil
    end
    local function releaseReceipt()
        local receipt = owner:Receipt()
        if receipt then pcall(methods.Release, receipt.sequence) end
    end
    function result:Enrich(raw)
        local enriched = copy(raw)
        enriched.heistControllerProof = nil
        if closed or type(raw.native) ~= "table" or raw.native.fullSync ~= true then return enriched end
        for _, field in ipairs({"session", "account", "place", "release"}) do
            if raw[field] ~= deps.identity[field] then return enriched end
        end
        local active = owner:Active()
        if active and not active.sent then owner:RecoverPrepared() end
        releaseReceipt()
        local value = native()
        if value then
            local proof = {sequence = value.sequence, controllersClear = value.controllersClear == true}
            for _, field in ipairs(headers) do proof[field] = raw[field] end
            enriched.heistControllerProof = proof
        end
        latest = enriched
        return enriched
    end
    local function canDispatch(proposal)
        local active, value = activeFor(proposal), native()
        if not active or not value or value.controllersClear ~= true or value.sequence ~= active.sequence - 1
            or type(latest) ~= "table" then return false end
        for _, field in ipairs({"session", "account", "place", "release", "revision"}) do
            if proposal[field] ~= latest[field] then return false end
        end
        local observed = latest
        if proposal.feature == "favors" or proposal.feature == "sabotage" then
            if not accounting then return false end
            for field, method in pairs(accountingMethods) do if accounting[field] ~= method then return false end end
            local saved = accountingMethods.Recovery(accounting, proposal.actionKey)
            if not saved or not matched(proposal, saved) or not same(saved.baseline, active.recovery.baseline)
                or saved.reply ~= nil then return false end
            local field = proposal.feature == "favors" and "favorUsageProof" or "sabotageUsageProof"
            local method = proposal.feature == "favors" and accountingMethods.FavorUsage or accountingMethods.SabotageUsage
            local proof = method(accounting, proposal.intent.serverDay, latest.capturedAt)
            if type(proof) ~= "table" or proof.account ~= proposal.account or proof.day ~= proposal.intent.serverDay
                or proof.capturedAt ~= latest.capturedAt or proof.attempts ~= proposal.intent.usageAttemptsBefore + 1 then return false end
            -- The exact checkpoint record proves this one already-counted charge.
            -- Rebuild only its pre-send view; never alter durable attempt usage.
            observed, proof = copy(latest), copy(proof)
            proof.attempts = proposal.intent.usageAttemptsBefore
            observed[field] = proof
        end
        local baseline = evidence[proposal.feature].capture(proposal, observed)
        if not baseline or not same(baseline, active.recovery.baseline) then return false end
        if proposal.feature == "heistCollect" then
            local now = value.serverNow
            if type(now) ~= "number" or now ~= now or now < 0 or now > 9007199254740991
                or math.floor(now / 86400) ~= proposal.intent.serverDay
                or value.sequence ~= proposal.intent.controllerSequenceBefore then return false end
        end
        return true
    end
    local lifecycle = {
        prepare = function(proposal, before, baseline, now)
            local value = native()
            if not value then return false, "Current native Heist context required" end
            return owner:Prepare(proposal, before, baseline, value, now)
        end,
        authorize = function(proposal, _, now)
            if not canDispatch(proposal) then return nil, "Heist preflight changed" end
            local call, reason = owner:MarkSending(proposal, native(), now)
            if not call then return nil, reason end
            local sequence, actionKey = call.nativeSequence, proposal.actionKey
            call.recordHeistReturn = function(reply)
                if closed then return false end
                return owner:AcceptReply(actionKey, sequence, reply)
            end
            return call, nil
        end,
        returned = function(proposal, reply)
            local active = activeFor(proposal)
            if not active then return false, "Heist reply owner changed" end
            return owner:AcceptReply(proposal.actionKey, active.sequence, reply)
        end,
        resolve = function(proposal, outcome, after)
            local active = activeFor(proposal)
            if not active then return false, "Heist outcome owner changed" end
            if outcome == "skipped_unconfirmed" then return true, nil end -- Keep both ledger and checkpoint hold.
            local saved, reason = owner:Resolve(proposal.actionKey, active.sequence, outcome, after)
            if saved then releaseReceipt() end
            return saved, reason
        end,
        unsent = function(proposal)
            local active = activeFor(proposal)
            local receipt = not active and owner:Receipt()
            local sequence = active and active.sequence or receipt and matched(proposal, receipt.recovery) and receipt.sequence
            if not sequence then return false, "Heist unsent owner changed" end
            return owner:CancelUnsent(proposal.actionKey, sequence)
        end,
    }
    lifecycle.abandonedUnsent = lifecycle.unsent
    local function recoverSaved(data, after)
        if closed or type(data) ~= "table" then return nil end
        local receipt = owner:Receipt()
        if receipt and matched(data.proposal, receipt.recovery) and same(data.baseline, receipt.recovery.baseline) then
            releaseReceipt()
            return receipt.outcome
        end
        local active = activeFor(data.proposal)
        if not active or not same(data.baseline, active.recovery.baseline) then return nil end
        if not active.sent then
            local saved = owner:RecoverPrepared()
            return saved and "known_unsent" or nil
        end
        local saved = active.recovery
        local reader = evidence[data.proposal.feature]
        local outcome = reader.evaluate(saved.proposal, saved.before, after, saved.reply, saved.baseline)
        if outcome ~= "confirmed" and outcome ~= "rejected" and type(reader.recoverSaved) == "function" then
            outcome = reader.recoverSaved(saved, after)
        end
        if outcome ~= "confirmed" and outcome ~= "rejected" then return nil end
        local resolved = owner:Resolve(data.proposal.actionKey, active.sequence, outcome, after, true)
        if resolved then releaseReceipt(); return outcome end
        return nil
    end
    lifecycle.recover = recoverSaved
    function result:Feature(original)
        local spec = copy(original)
        local planner = original.id == "heistCollect" and collection or original.planner
        spec.reader = original.id == "heistCollect" and collection or original.reader
        spec.evidence = evidence[original.id]
        spec.planner = {propose = function(view, settings, reservations)
            local value = native()
            if owner:Active() or not value or value.controllersClear ~= true then return nil, "Native Heist queue or durable action still owned" end
            return planner.propose(view, settings, reservations)
        end}
        spec.lifecycle, spec.canDispatch, spec.recoverSaved = lifecycle, canDispatch, recoverSaved
        return spec
    end
    function result:ReadSources()
        return {{id = "heistStatus", interval = 3,
            enabled = function()
                local active = owner:RecoveryRecord()
                return not closed and active ~= nil and active.recovery.reply == nil
            end,
            prepare = function()
                if not native() or methods.Busy() then return nil, "Native Heist worker still running" end
                return deps.SequenceRecovery.statusCall(owner:RecoveryRecord(), deps.identity)
            end,
            accept = function(_, request, reply)
                local active = owner:RecoveryRecord()
                if not active or active.sequence ~= request.args[3] or active.actionKey ~= request.actionKey
                    or deps.SequenceRecovery.classify(reply) ~= "reported" then return nil end
                return {actionKey = active.actionKey, sequence = active.sequence, reply = reply}
            end,
            commit = function(staged) return not closed and owner:AcceptReply(staged.actionKey, staged.sequence, staged.reply) end,
        }}
    end
    function result:Close() if closed then return end; closed = true; latest = nil; owner:Close() end
    return result, nil
end
return Runtime
