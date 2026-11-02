-- Source-backed rank transition only; durable attempt/controller ownership is Task 24.
local PrestigeReset = {}
local MAX = 9007199254740991
local headers = { "session", "account", "place", "release", "revision", "capturedAt" }
local function number(value, low, high)
    return type(value) == "number" and value == value and value >= low and value <= high
end
local function integer(value, low, high)
    return number(value, low, high) and value % 1 == 0
end
local function identity(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0 or #a[field] > 200
            or a[field] ~= b[field] then return false end
    end
    return true
end
local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for key, value in pairs(a) do if b[key] ~= value then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function plan(view, settings, reader)
    if type(settings) ~= "table" or settings.enabled ~= true then return nil, "Prestige disabled" end
    if type(view) ~= "table" or not identity(view, view)
        or view.catalogKey ~= reader.key or view.release ~= reader.release
        or not integer(view.revision, 0, MAX) or not number(view.capturedAt, 0, MAX)
        or not integer(view.rank, 0, 6) or not integer(view.level, 1, MAX)
        or view.xpKnown ~= true or not number(view.xp, 0, MAX)
        or not integer(settings.targetRank, 1, 6) or not integer(settings.maxResets, 0, 6)
        or type(settings.allowReset) ~= "boolean" then return nil, "Current Prestige level/EXP and reset limits required" end
    local preview = view.preview or "Prestige preview unavailable"
    if settings.allowReset ~= true then return nil, preview .. "; explicit reset choice is off" end
    if view.rank >= settings.targetRank or view.rank >= 6 then return nil, preview .. "; target rank reached" end
    if view.ready ~= true or view.nextRank ~= view.rank + 1
        or not integer(view.requiredLevel, 1, MAX)
        or view.requiredLevel ~= reader.levels[view.nextRank] or view.level < view.requiredLevel then
        return nil, preview .. "; next rank level requirement not met"
    end
    if not integer(view.attempted, 0, 6) or view.controllersClear ~= true then
        return nil, preview .. "; durable usage and native controller-clear proof required"
    end
    if view.attempted >= settings.maxResets then return nil, preview .. "; reset attempt cap reached" end
    return { session = view.session, account = view.account, place = view.place,
        release = view.release, revision = view.revision, feature = "prestige",
        actionKey = "prestige:" .. view.rank .. ":" .. view.nextRank, resources = {},
        intent = { kind = "prestigeReset", rankBefore = view.rank, nextRank = view.nextRank,
            levelBefore = view.level, xpBefore = view.xp, catalogKey = view.catalogKey,
            requiredLevel = view.requiredLevel, allowReset = true, targetRank = settings.targetRank,
            maxResets = settings.maxResets, attemptedBefore = view.attempted } }, nil
end

function PrestigeReset.new(reader)
    assert(type(reader) == "table" and type(reader.read) == "function"
        and type(reader.key) == "string" and #reader.key == 64
        and reader.key:match("^[%x]+$") and type(reader.levels) == "table" and #reader.levels == 6
        and type(reader.release) == "string" and #reader.release > 0, "Current Prestige reader required")
    local result = {}
    result.propose = function(view, settings) return plan(view, settings, reader) end
    result.capture = function(proposal, before)
        local intent = type(proposal) == "table" and proposal.intent
        local view = reader.read(before, before)
        if not view or type(intent) ~= "table" or not identity(proposal, view)
            or proposal.revision ~= view.revision or proposal.feature ~= "prestige"
            or type(proposal.resources) ~= "table" or next(proposal.resources) ~= nil then
            return nil, "Prestige baseline identity or exposure changed"
        end
        local planned = plan(view, { enabled = true, allowReset = intent.allowReset,
            targetRank = intent.targetRank, maxResets = intent.maxResets }, reader)
        if not planned or planned.actionKey ~= proposal.actionKey or not same(planned.intent, intent) then
            return nil, "Prestige rank/level/EXP, catalog, usage or limits changed"
        end
        local baseline = {}
        for key, value in pairs(view) do baseline[key] = value end
        baseline.actionKey = proposal.actionKey
        baseline.intent = {}
        for key, value in pairs(intent) do baseline.intent[key] = value end
        return baseline, nil
    end
    result.evaluate = function(proposal, before, after, reply, baseline)
        local intent = type(proposal) == "table" and proposal.intent
        if type(baseline) ~= "table" or type(intent) ~= "table" or type(reply) ~= "table"
            or not integer(baseline.rank, 0, 5) or not integer(baseline.level, 1, MAX)
            or not number(baseline.xp, 0, MAX) or baseline.xpKnown ~= true
            or not identity(proposal, baseline) or not identity(before, baseline)
            or not identity(after, baseline) or proposal.feature ~= "prestige"
            or proposal.actionKey ~= baseline.actionKey
            or proposal.revision ~= baseline.revision or before.revision ~= baseline.revision
            or type(proposal.resources) ~= "table" or next(proposal.resources) ~= nil
            or not same(intent, baseline.intent) then return "pending" end
        for _, field in ipairs(headers) do
            if before[field] ~= baseline[field] then return "pending" end
        end
        local current = reader.read(after, after)
        if not current or not current.xpKnown or current.catalogKey ~= baseline.catalogKey then return "pending" end
        local unchanged = current.rank == baseline.rank and current.level == baseline.level and current.xp == baseline.xp
        if reply.pending == true or reply.code == "rate_limited" or reply.code == "busy" or reply.code == "presence" then return "pending" end
        if reply.ok == false then return unchanged and "rejected" or "pending" end
        if reply.ok == true and reply.pending ~= true and reply.code ~= "rate_limited"
            and reply.rank == intent.nextRank and integer(current.revision, baseline.revision + 1, MAX)
            and current.rank == baseline.rank + 1 and current.level == 1 and current.xp == 0 then
            return "confirmed"
        end
        return "pending"
    end
    function result.recoverSaved(data, after)
        if type(data) ~= "table" or type(data.proposal) ~= "table" or type(data.before) ~= "table"
            or type(data.baseline) ~= "table" or type(data.reply) ~= "table" or type(after) ~= "table" then return nil end
        local captured = result.capture(data.proposal, data.before)
        if not captured or not same(captured.intent, data.baseline.intent) then return nil end
        for key, value in pairs(captured) do if key ~= "intent" and data.baseline[key] ~= value then return nil end end
        for key in pairs(data.baseline) do if captured[key] == nil then return nil end end
        local before, p, reply = data.baseline, data.proposal, data.reply
        for _, key in ipairs({"account", "place", "release"}) do if after[key] ~= p[key] then return nil end end
        if type(after.session) ~= "string" or #after.session < 1 or #after.session > 200
            or after.session == p.session and (not integer(after.revision, before.revision + 1, MAX))
            or type(after.native) ~= "table" or type(data.before.native) ~= "table"
            or not number(after.native.serverNow, 0, MAX) or not number(data.before.native.serverNow, 0, MAX)
            or after.native.serverNow < data.before.native.serverNow then return nil end
        local current = reader.read(after, after)
        if not current or not current.xpKnown or current.catalogKey ~= before.catalogKey
            or reply.pending == true or reply.code == "rate_limited" or reply.code == "busy" or reply.code == "presence" then return nil end
        if reply.ok == true and reply.rank == before.rank + 1 and current.rank == before.rank + 1
            and current.level == 1 and current.xp == 0 then return "confirmed" end
        if reply.ok == false and current.rank == before.rank and current.level == before.level and current.xp == before.xp then
            return "rejected"
        end
        return nil
    end
    return result
end

function PrestigeReset.describe(proposal)
    local intent = type(proposal) == "table" and proposal.intent
    if type(intent) ~= "table" or proposal.feature ~= "prestige" or intent.kind ~= "prestigeReset"
        or not integer(intent.rankBefore, 0, 5) or intent.nextRank ~= intent.rankBefore + 1
        or intent.allowReset ~= true or not integer(intent.targetRank, intent.nextRank, 6)
        or not integer(intent.maxResets, 1, 6) or not integer(intent.attemptedBefore, 0, intent.maxResets - 1)
        or not integer(intent.levelBefore, 1, MAX) or not number(intent.xpBefore, 0, MAX)
        or not integer(intent.requiredLevel, 1, intent.levelBefore)
        or type(intent.catalogKey) ~= "string" or #intent.catalogKey ~= 64
        or not intent.catalogKey:match("^[%x]+$")
        or type(proposal.resources) ~= "table" or next(proposal.resources) ~= nil then
        return nil, "Reviewed explicitly opted-in Prestige reset required"
    end
    local allowed = { kind = true, rankBefore = true, nextRank = true, levelBefore = true,
        xpBefore = true, catalogKey = true, requiredLevel = true, allowReset = true,
        targetRank = true, maxResets = true, attemptedBefore = true }
    for field in pairs(intent) do
        if not allowed[field] then return nil, "Unknown Prestige reset intent field" end
    end
    return { remote = "PrestigeAction", method = "InvokeServer", arity = 1,
        args = { "prestige" }, source = "saved PrestigeModal confirmed reset call" }, nil
end

return PrestigeReset
