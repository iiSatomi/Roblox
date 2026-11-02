-- Explicit local saved-record cleanup. No scheduler, remote, purchase or dismissal.
local CrewRecoveryReview = {}
local fields = {"session", "account", "place", "release", "revision", "feature", "actionKey"}
function CrewRecoveryReview.new(deps)
    local owner, helper, env = deps.owner, deps.helper, deps.environment
    assert(type(owner) == "table" and type(helper) == "table" and type(env) == "table"
        and type(env.checkpoint) == "table" and type(env.session) == "table"
        and type(env.currentSnapshot) == "function" and type(env.requested) == "function"
        and type(env.busy) == "function" and type(env.clock) == "table", "Missing Crew review owners")
    local closed, busy, staged = false, false, nil
    local function time()
        local ok, now = pcall(env.clock.Now, env.clock)
        return ok and type(now) == "number" and now == now and now >= 0 and now < math.huge and now or nil
    end
    local function paused()
        local state = env.session:Status()
        return not closed and state.state == "paused" and state.active == nil and env.requested() == false
            and not state.storageFault and not env.checkpoint.fault
    end
    local function guard()
        if busy or env.busy() or not paused() then return nil, "Pause and finish active work before reviewing Crew recovery" end
        local raw = env.currentSnapshot()
        if type(raw) ~= "table" or type(raw.native) ~= "table" or raw.native.fullSync ~= true then
            return nil, "Current full account information required"
        end
        for _, key in ipairs({"session", "account", "place", "release"}) do
            if raw[key] ~= env.identity[key] then return nil, "Crew recovery account changed" end
        end
        local active, usage = owner:Active(), owner:Usage()
        if not active or not usage then return nil, "No reviewable saved Crew record" end
        local now = time()
        if now == nil then return nil, "Crew recovery timer unavailable" end
        local kind, description
        local knownUnsent = owner:KnownUnsent()
        if active.stage == "preparedDismiss" or knownUnsent and active.stage == "sentDismiss" then
            kind, description = "discardDismiss", "Release the unsent dismissal and restore its reserved attempt. No game action."
        elseif active.stage == "preparedHire" or knownUnsent and active.stage == "sentHire" then
            kind, description = "restoreHire", "Restore the saved empty slot and keep its funded hire and counted attempt. No game action."
        elseif active.stage == "sentHire" and type(active.reply) == "table" and active.reply.ok == false
            and active.reply.pending ~= true and type(raw.capturedAt) == "number"
            and raw.capturedAt <= now and now - raw.capturedAt <= 2
            and helper.reconcile(active.proposal, active.baseline, raw, active.reply, true) == "rejected" then
            kind, description = "releaseRejectedHire", "Release rejected-hire custody. Counted attempt and Cash exposure stay; no automatic retry."
        else return nil, "Sent outcome remains held; no discard or replay is authorized" end
        local checkpointed = false
        for _, record in ipairs(env.checkpoint:Records()) do
            if record.feature == "crewRoll" then
                if checkpointed or record.actionKey ~= active.proposal.actionKey then return nil, "Other Crew uncertainty needs review" end
                local data = env.checkpoint:Recovery(record.actionKey)
                if not data or not helper.Same(data.baseline, active.baseline)
                    or not helper.Same(data.proposal.intent, active.proposal.intent)
                    or not helper.Same(data.proposal.resources, active.proposal.resources) then return nil, "Crew checkpoint does not match this saved record" end
                for _, key in ipairs(fields) do
                    if data.proposal[key] ~= active.proposal[key] then return nil, "Crew checkpoint identity changed" end
                end
                if kind ~= "releaseRejectedHire" and data.reply ~= nil then return nil, "Prepared Crew record has a returned result" end
                checkpointed = true
            end
        end
        return {kind = kind, description = description, slot = active.funded.slot, generation = owner.generation,
            actionKey = active.proposal.actionKey, checkpointed = checkpointed, raw = raw,
            attempted = usage.attempted, spent = usage.spent, at = now, knownUnsent = knownUnsent}, nil
    end
    local result = {}
    function result:Preview()
        staged = nil
        local view, why = guard()
        if not view then return nil, why end
        local ticket = {}
        staged = {view = view, ticket = ticket, at = view.at}
        return {kind = view.kind, slot = view.slot, description = view.description,
            attempted = view.attempted, spent = view.spent, ticket = ticket}, nil
    end
    function result:Confirm(ticket)
        local preview = staged
        staged = nil
        if not preview or preview.ticket ~= ticket then return false, "Review this Crew record before confirming" end
        local view, why = guard()
        local now = time()
        if not view then return false, why end
        if now == nil or now < preview.at or now - preview.at > 30 then return false, "Crew recovery review expired" end
        for _, key in ipairs({"kind", "generation", "actionKey", "attempted", "spent", "checkpointed", "knownUnsent"}) do
            if view[key] ~= preview.view[key] then return false, "Saved Crew record changed; review again" end
        end
        busy = true
        local ok, saved, failure = pcall(function()
            local accepted, reason
            if view.knownUnsent then accepted, reason = owner:RecoverKnownUnsent()
            elseif view.kind == "discardDismiss" then accepted, reason = owner:DiscardPrepared()
            elseif view.kind == "restoreHire" then accepted, reason = owner:RestorePreparedHire()
            else accepted, reason = owner:ReleaseRejectedHire(view.raw, now) end
            if accepted ~= true then return false, reason end
            if not paused() then return false, "Local recovery saved; remaining cleanup waits for a current paused session" end
            if view.checkpointed then
                return env.checkpoint:Resolve(view.actionKey, view.kind == "releaseRejectedHire" and "rejected" or "schedule_failed")
            end
            return true
        end)
        busy = false
        if not ok then return false, "Crew recovery save failed" end
        return saved == true, failure
    end
    function result:Invalidate() staged = nil end
    function result:IsBusy() return busy end
    function result:Close() closed, staged = true, nil end
    return result
end
return CrewRecoveryReview
