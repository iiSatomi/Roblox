-- Staged native fight payouts belong to an exact leased outgoing Attack reply.
-- No allocator, scheduler, mutation, replay or aggregate-balance inference.
local FightReceipts = {}
local MAX = 9007199254740991
local identities = {"session", "account", "place", "release"}
local numbers = {"cashEstimate", "cashConfirmed", "cashLost", "stolen", "respectEstimate",
    "respect", "respectLost", "xp", "xpEstimate", "xpEventMultiplier", "dmgDealt",
    "dmgTaken", "staminaCost", "targetLevel", "targetShownLevel"}
local booleans = {"ok", "won", "cashPending", "rewardsPending", "cashAdjusted", "knockout"}
local function number(v, low, high)
    return type(v) == "number" and v == v and v >= low and v <= high
end
local function integer(v, low, high) return number(v, low, high) and v % 1 == 0 end
local function text(v, high)
    return type(v) == "string" and #v > 0 and #v <= high and not v:find("[%c]")
end
local function clone(v)
    if type(v) ~= "table" then return v end
    local out = {}
    for k, child in pairs(v) do out[k] = clone(child) end
    return out
end
local function equal(a, b)
    for k, v in pairs(a) do
        if type(v) == "table" then
            if type(b[k]) ~= "table" or not equal(v, b[k]) then return false end
        elseif b[k] ~= v then return false end
    end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end
local function packet(raw)
    if type(raw) ~= "table" or not text(raw.fightId, 160)
        or not integer(raw.cashStage, 1, 4) or type(raw.ok) ~= "boolean"
        or type(raw.cashPending) ~= "boolean" or type(raw.rewardsPending) ~= "boolean" then return nil end
    local out = {fightId = raw.fightId, cashStage = raw.cashStage}
    for _, k in ipairs(numbers) do
        local v = raw[k]
        if v ~= nil and not integer(v, 0, MAX) then return nil end
        out[k] = v
    end
    for _, k in ipairs(booleans) do
        local v = raw[k]
        if v ~= nil and type(v) ~= "boolean" then return nil end
        out[k] = v
    end
    if raw.targetName ~= nil and not text(raw.targetName, 64) then return nil end
    out.targetName = raw.targetName
    if raw.targetDaily ~= nil then
        if type(raw.targetDaily) ~= "table" then return nil end
        out.targetDaily = {}
        for _, k in ipairs({"day", "count", "resetAt", "serverNow"}) do
            local v = raw.targetDaily[k]
            if v ~= nil and ((k == "day" or k == "count") and not integer(v, 0, MAX)
                or (k == "serverNow" or k == "resetAt") and not number(v, 0, MAX)) then return nil end
            out.targetDaily[k] = v
        end
    end
    return out
end
local function settled(p)
    return p.ok == true and type(p.won) == "boolean" and p.cashStage == 4
        and p.cashPending == false and p.rewardsPending == false
        and integer(p.cashConfirmed, 0, MAX) and integer(p.stolen, 0, MAX)
        and p.stolen == p.cashConfirmed and integer(p.xp, 0, MAX)
        and integer(p.respect, 0, MAX) and integer(p.staminaCost, 1, 5)
end
FightReceipts.Project = packet
FightReceipts.Settled = settled

function FightReceipts.new(identity, clock, lane, source, fingerprint)
    assert(type(identity) == "table" and type(clock) == "table" and type(clock.Now) == "function"
        and type(lane) == "table" and type(lane.Owns) == "function" and type(lane.Status) == "function"
        and type(source) == "table" and type(source.Subscribe) == "function" and type(source.Current) == "function"
        and type(fingerprint) == "string" and #fingerprint == 64 and fingerprint:match("^[%x]+$"),
        "Missing current fight receipt dependencies")
    local bound = {}
    for _, k in ipairs(identities) do assert(text(identity[k], 200), "Invalid fight receipt scope"); bound[k] = identity[k] end
    local active, connection, closed, generation = nil, nil, false, 0
    local persistence, persisting = nil, false
    local function retire()
        generation = generation + 1
        active = nil
        if connection then pcall(connection.Disconnect, connection); connection = nil end
    end
    local function current()
        if closed then return false end
        local ok, value = pcall(source.Current, source)
        return ok and value == true
    end
    local function owns(row)
        return row ~= nil and current() and lane:Owns(row.token)
    end
    local function accept(row, p)
        if not row.initial or p.fightId ~= row.initial.fightId then return false end
        if p.targetName ~= nil and p.targetName ~= row.initial.targetName then row.ambiguous = true; return false end
        for _, k in ipairs({"targetLevel", "targetShownLevel", "staminaCost"}) do
            if p[k] ~= nil and p[k] ~= row.initial[k] then row.ambiguous = true; return false end
        end
        if p.ok ~= true or p.won ~= row.initial.won then row.ambiguous = true end
        local previous = row.receipt
        if p.cashStage < previous.cashStage then return false end
        if p.cashStage == previous.cashStage then
            if not equal(p, previous) then row.ambiguous = true end
            return false
        end
        row.receipt = p
        return true
    end
    local function persist()
        local row = active
        if persisting or not persistence or not owns(row) or row.persisted or row.ambiguous
            or not row.initial or not settled(row.receipt) then return end
        persisting = true
        local ok, saved = pcall(persistence)
        persisting = false
        if ok and saved == true and active == row then row.persisted = true end
    end
    local function receive(kind, _, raw)
        local row = active
        if kind ~= "fightcash" or not owns(row) or row.sealed then return end
        local p = packet(raw)
        if not p then return end
        if row.initial then accept(row, p); persist(); return end
        if #row.buffer >= 32 then row.ambiguous = true; return end
        row.buffer[#row.buffer + 1] = p
    end
    local result = {sourceKey = fingerprint:lower(), release = bound.release}
    function result:SetPersistence(callback)
        if closed or persistence ~= nil or type(callback) ~= "function" then return false end
        persistence = callback
        return true
    end
    -- Called again after the initial reply is durable: a terminal notification
    -- can arrive while InvokeServer is still returning and was buffered above.
    function result:Persist() persist() end
    function result:Begin(token, proposal, target)
        local status = lane:Status()
        if not current() or not lane:Owns(token) or not status.active or status.active.kind ~= "mutation"
            or type(proposal) ~= "table" or (proposal.feature ~= "combat" and proposal.feature ~= "warCombat")
            or proposal.actionKey ~= status.active.actionKey or not integer(target, 1, MAX)
            or type(proposal.intent) ~= "table" or proposal.intent.kind ~= "playerAttack"
            or proposal.intent.target ~= target or type(proposal.resources) ~= "table"
            or not integer(proposal.resources.stamina, 1, 5) then return false, "No exact owned outgoing player attack" end
        local quote, exposure = proposal.intent.expectedStaminaCost, proposal.intent.maxStaminaExposure
        if quote == nil then quote = proposal.resources.stamina end
        if not integer(quote, 1, proposal.resources.stamina)
            or exposure ~= nil and (exposure ~= proposal.resources.stamina or proposal.intent.expectedStaminaCost == nil)
            or exposure == nil and quote ~= proposal.resources.stamina then return false, "Fight quote or maximum reservation changed" end
        for key in pairs(proposal.resources) do
            if key ~= "stamina" then return false, "Player fight has an unsupported resource charge" end
        end
        for _, k in ipairs(identities) do if proposal[k] ~= bound[k] then return false, "Fight scope changed" end end
        if type(source.CanAttack) ~= "function" then return false, "Current native execution guard unavailable" end
        local guarded, allowed, why = pcall(source.CanAttack, source, proposal, target)
        if not guarded or allowed ~= true then return false, guarded and why or "Native fight guard raised" end
        if active and owns(active) then return false, "Another fight receipt owns the lane" end
        if active or connection then retire() end
        if not connection then
            generation = generation + 1
            local subscribedGeneration = generation
            local ok, value = pcall(source.Subscribe, source, function(...)
                if generation == subscribedGeneration then receive(...) end
            end)
            if not ok or not value or type(value.Disconnect) ~= "function" then return false, "Fight notifications unavailable" end
            connection = value
        end
        if not current() or not lane:Owns(token) then return false, "Fight receipt lease changed" end
        active = {token = token, actionKey = proposal.actionKey, target = target, feature = proposal.feature,
            sentAt = status.active.acquiredAt, expectedStamina = quote, buffer = {}}
        return true, nil
    end
    function result:CheckScout(token, proposal, target)
        local status = lane:Status()
        local i = type(proposal) == "table" and proposal.intent
        if not current() or not lane:Owns(token) or not status.active or status.active.kind ~= "mutation"
            or type(i) ~= "table" or i.kind ~= "playerScout" or i.target ~= target or not integer(target, 1, MAX)
            or (proposal.feature ~= "combat" and proposal.feature ~= "warCombat")
            or proposal.actionKey ~= status.active.actionKey or type(source.CanScout) ~= "function" then
            return false, "Exact owned Scout dispatch required"
        end
        for _, k in ipairs(identities) do if proposal[k] ~= bound[k] then return false, "Scout scope changed" end end
        local ok, allowed, why = pcall(source.CanScout, source, proposal, target)
        if not ok or allowed ~= true or not current() or not lane:Owns(token) then
            return false, ok and why or "Native Scout guard unavailable"
        end
        return true, nil
    end
    function result:Bind(token, raw)
        local row = active
        if not owns(row) or row.token ~= token then return false, "Fight receipt owner changed" end
        if row.sealed then return false, "Fight receipt already finalized" end
        local p = packet(raw)
        if type(source.HandleReply) == "function" then pcall(source.HandleReply, source, raw) end
        if not p or p.cashStage ~= 1 or p.ok ~= true or type(p.won) ~= "boolean"
            or not text(p.targetName, 64) or not integer(p.staminaCost, 1, 5) then
            row.ambiguous = true; return false, "Initial fight reply unavailable" end
        if row.initial then
            if not equal(row.initial, p) then row.ambiguous = true; return false, "Initial fight reply changed" end
            return true, nil
        end
        row.initial, row.receipt = p, p
        if p.staminaCost ~= row.expectedStamina then row.ambiguous = true end
        for _, pending in ipairs(row.buffer) do accept(row, pending) end
        row.buffer = {}
        if p.staminaCost ~= row.expectedStamina then return false, "Native Stamina charge differs from reservation" end
        return true, nil
    end
    -- Same terminal acceptance as graceful close, without discarding the proof
    -- that normal reconciliation still needs. Seal before Disconnect can yield.
    function result:Seal(attempt)
        local row = active
        if type(attempt) ~= "table" or not owns(row) or active ~= row or row.ambiguous
            or not row.initial or not settled(row.receipt) or attempt.status ~= "settled"
            or attempt.actionKey ~= row.actionKey or attempt.target ~= row.target
            or attempt.feature ~= row.feature or not equal(attempt.initial, row.initial)
            or not equal(attempt.receipt, row.receipt) then return false end
        if row.sealed then return true end
        row.sealed = true
        generation = generation + 1
        local previous = connection
        connection = nil
        if previous then pcall(previous.Disconnect, previous) end
        return active == row and not closed
    end
    function result:Release(token)
        if active and active.token == token then retire(); return true end
        return false
    end
    function result:Read(snapshot)
        if not current() then retire(); return nil end
        if active and not lane:Owns(active.token) then retire() end
        if type(snapshot) ~= "table" then return nil end
        for _, k in ipairs(identities) do if snapshot[k] ~= bound[k] then return nil end end
        if not integer(snapshot.revision, 0, MAX) or type(snapshot.capturedAt) ~= "number"
            or snapshot.capturedAt ~= snapshot.capturedAt or snapshot.capturedAt < 0
            or snapshot.capturedAt > MAX then return nil end
        local out = {sourceKey = self.sourceKey, revision = snapshot.revision, capturedAt = snapshot.capturedAt, attempts = {}}
        for _, k in ipairs(identities) do out[k] = bound[k] end
        if owns(active) and active.initial then
            out.attempts[1] = {actionKey = active.actionKey, target = active.target, feature = active.feature,
                sentAt = active.sentAt, initial = clone(active.initial), receipt = clone(active.receipt),
                status = active.ambiguous and "ambiguous" or settled(active.receipt) and "settled" or "pending"}
        end
        return out
    end
    function result:Close()
        persistence = nil
        if closed then return false end
        closed = true
        retire()
        return true
    end
    return result
end
return FightReceipts
