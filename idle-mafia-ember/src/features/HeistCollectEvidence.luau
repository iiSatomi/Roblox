-- Exact original result, controller scope, and complete reward custody.
local HeistCollectEvidence = {}
local MAX = 9007199254740991
local identity = {"session", "account", "place", "release"}
local scope = {"nativeJob", "nativeEpoch", "nativeSourceKey"}
local function number(value)
    return type(value) == "number" and value == value and value >= 0 and value <= MAX
end
local function integer(value, minimum) return number(value) and value >= minimum and value % 1 == 0 end
local function text(value, limit)
    return type(value) == "string" and #value > 0 and #value <= (limit or 120) and not value:find("[%c]")
end
local function hash(value) return text(value, 64) and #value == 64 and value:match("^[%x]+$") ~= nil end
local function same(a, b, restart)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs(identity) do
        if not text(a[field], 200) or not text(b[field], 200)
            or (not restart or field ~= "session") and a[field] ~= b[field] then return false end
    end
    return true
end
local function header(a, b)
    return same(a, b) and a.revision == b.revision and a.capturedAt == b.capturedAt
end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function copied(raw)
    local seen, nodes = {}, 0
    local function copy(value, depth)
        nodes = nodes + 1
        if nodes > 4096 or depth > 8 then error("Heist result exceeds limits") end
        local kind = type(value)
        if kind == "table" then
            if seen[value] or getmetatable(value) ~= nil then error("Invalid Heist result graph") end
            seen[value] = true
            local result = {}
            for key, item in pairs(value) do
                if not (type(key) == "string" and #key <= 1000 or integer(key, 0)) then error("Invalid result key") end
                result[key] = copy(item, depth + 1)
            end
            seen[value] = nil
            return result
        end
        if type(value) == "number" then
            if value ~= value or value < -MAX or value > MAX then error("Invalid result number") end
            return value
        end
        if kind == "string" and #value <= 16384 or kind == "boolean" or kind == "nil" then return value end
        error("Invalid Heist result value")
    end
    local ok, value = pcall(copy, raw, 0)
    return ok and value or nil
end
local function inventory(raw)
    if type(raw) ~= "table" then return nil end
    local result, size = {}, 0
    for id, amount in pairs(raw) do
        size = size + 1
        if size > 4096 or not text(id) or not integer(amount, 0) then return nil end
        result[id] = amount
    end
    return result
end
local function current(raw)
    local native = type(raw) == "table" and raw.native
    local proof = type(raw) == "table" and raw.heistBoardProof
    local protocol = type(raw) == "table" and raw.heistProtocolProof
    local board = type(proof) == "table" and proof.board
    if type(native) ~= "table" or native.fullSync ~= true or not number(native.serverNow)
        or not integer(raw.revision, 0) or not number(raw.capturedAt)
        or type(proof) ~= "table" or proof.account ~= raw.account or proof.capturedAt ~= raw.capturedAt
        or proof.query ~= nil or not hash(proof.sourceKey) or not header(proof.header, raw)
        or type(board) ~= "table" or board.ok ~= true or type(board.rows) ~= "table"
        or not number(board.serverNow) or math.abs(board.serverNow - native.serverNow) > 2
        or type(protocol) ~= "table" or not header(protocol, raw)
        or not integer(protocol.controllerCounter, 0) or not text(protocol.nativeJob)
        or not text(protocol.nativeEpoch) or not hash(protocol.nativeSourceKey)
        or (board.result ~= nil and (type(board.result) ~= "table" or not hash(protocol.resultKey)
            or copied(board.result) == nil))
        or (board.result == nil and protocol.resultKey ~= nil) then return nil end
    return native, board, protocol, proof
end
local function rewardSpec(result)
    if type(result) ~= "table" or not text(result.heistId) or type(result.ok) ~= "boolean" then return nil end
    local reward = {items = {}}
    for _, field in ipairs({"cash", "xp", "gold", "crates", "bonusCrates"}) do
        local value = result[field]
        if result.ok then
            if not integer(value, 0) then return nil end
        elseif value ~= nil and value ~= 0 then return nil end
        -- Failure renderer explicitly hides all rewards and says the stake is lost.
        reward[field] = result.ok and value or 0
    end
    local function add(id, amount)
        if id ~= nil and not text(id) then return false end
        if amount == 0 then return true end
        if not text(id) then return false end
        reward.items[id] = (reward.items[id] or 0) + amount
        return reward.items[id] <= MAX
    end
    if not add("gold_bar", reward.gold) or not add(result.crateId, reward.crates)
        or not add(result.bonusCrateId, reward.bonusCrates) then return nil end
    return reward
end
local function projectXP(native, gain, thresholds)
    if not integer(native.level, 1) or not number(native.xp) or type(thresholds) ~= "table"
        or not integer(gain, 0) or native.xp + gain > MAX then return nil end
    local level, xp, used = native.level, native.xp + gain, {}
    for crossing = 0, 128 do
        local threshold = thresholds[level]
        if not integer(threshold, 1) or crossing == 0 and native.xp >= threshold then return nil end
        used[level] = threshold
        if xp < threshold then return {level = level, xp = xp, thresholds = used} end
        xp, level = xp - threshold, level + 1
    end
    return nil
end
local function validIntent(intent)
    return type(intent) == "table" and intent.kind == "heistCollect" and integer(intent.sequence, 1)
        and text(intent.nativeJob) and text(intent.nativeEpoch) and hash(intent.nativeSourceKey)
        and hash(intent.resultKey) and intent.runId == nil and intent.heistId == nil and intent.rowId == nil
end

function HeistCollectEvidence.capture(proposal, before)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal) ~= "table" or proposal.feature ~= "heistCollect" or not validIntent(intent)
        or type(before) ~= "table" or not same(proposal, before) or proposal.revision ~= before.revision
        or type(proposal.resources) ~= "table" then return nil, "Heist collection contract unverified" end
    for _, amount in pairs(proposal.resources) do if amount ~= 0 then return nil, "Collection cannot reserve a spend" end end
    local native, board, protocol, proof = current(before)
    local quote = protocol and protocol.quote
    if not native or board.mine ~= nil or type(board.result) ~= "table"
        or protocol.resultKey ~= intent.resultKey or protocol.controllerCounter ~= intent.sequence - 1
        or type(quote) ~= "table" or quote.sequence ~= intent.sequence then
        return nil, "Exact original Heist result and idle sequence required"
    end
    for _, field in ipairs(scope) do
        if protocol[field] ~= intent[field] or quote[field] ~= intent[field] then return nil, "Heist controller scope changed" end
    end
    local result = copied(board.result)
    local rewards = rewardSpec(result)
    local loose, bound = inventory(native.inventory), inventory(native.inventoryBound)
    local projection = rewards and projectXP(native, rewards.xp, protocol.xpThresholds)
    if not rewards or not loose or not bound or not projection or not number(native.cash)
        or native.cash + rewards.cash > MAX
        or (native.maxLevel ~= nil and not integer(native.maxLevel, native.level))
        or (native.prestige ~= nil and not integer(native.prestige, 0)) then
        return nil, "Complete Heist reward, XP thresholds and custody required"
    end
    return {session = proposal.session, account = proposal.account, place = proposal.place,
        release = proposal.release, revision = proposal.revision, capturedAt = before.capturedAt,
        serverNow = native.serverNow, boardServerNow = board.serverNow, boardSourceKey = proof.sourceKey,
        sequence = intent.sequence, nativeJob = intent.nativeJob, nativeEpoch = intent.nativeEpoch,
        nativeSourceKey = intent.nativeSourceKey, resultKey = intent.resultKey,
        result = result, rewards = rewards, inventory = loose, inventoryBound = bound,
        cash = native.cash, level = native.level, xp = native.xp, maxLevel = native.maxLevel,
        prestige = native.prestige, projection = projection, xpThresholds = copied(protocol.xpThresholds)}, nil
end

local function custody(native, protocol, baseline, unchanged, awardedProjection)
    local rewards = baseline.rewards
    local projection = awardedProjection or baseline.projection
    local level = unchanged and baseline.level or projection.level
    local xp = unchanged and baseline.xp or projection.xp
    local maxLevel = baseline.maxLevel ~= nil and math.max(baseline.maxLevel, level) or nil
    -- Passive Cash can accrue while the exact owned result is collected.
    -- Rejection still needs an unchanged balance; positive effects keep the
    -- quoted Cash floor plus exact result, controller, XP and item custody.
    if not number(native.cash) or (unchanged and native.cash ~= baseline.cash)
        or (not unchanged and native.cash < baseline.cash + rewards.cash)
        or native.level ~= level or native.xp ~= xp or native.maxLevel ~= maxLevel
        or native.prestige ~= baseline.prestige or type(protocol.xpThresholds) ~= "table"
        or protocol.xpThresholds[level] ~= projection.thresholds[level] then return false end
    for index, threshold in pairs(projection.thresholds) do
        if protocol.xpThresholds[index] ~= nil and protocol.xpThresholds[index] ~= threshold then return false end
    end
    local loose, bound = inventory(native.inventory), inventory(native.inventoryBound)
    if not loose or not bound then return false end
    local ids = {}
    for _, map in ipairs({baseline.inventory, baseline.inventoryBound, loose, bound, rewards.items}) do
        for id in pairs(map) do ids[id] = true end
    end
    for id in pairs(ids) do
        local dl = (loose[id] or 0) - (baseline.inventory[id] or 0)
        local db = (bound[id] or 0) - (baseline.inventoryBound[id] or 0)
        -- RewardEffects' unspecified-origin rule: preserve both existing origins.
        if dl < 0 or db < 0 or dl + db ~= (unchanged and 0 or rewards.items[id] or 0) then return false end
    end
    return true
end
local function terminalQuote(reply, baseline)
    local reward, result = baseline.rewards, baseline.result
    if reply.collected ~= result.ok then return false end
    -- The board quotes base XP; the owned terminal reply quotes the actual
    -- awarded XP after native bonuses. Its exact replicated effect is checked
    -- below using thresholds captured before this same action.
    if result.ok and (reply.cash ~= reward.cash or not integer(reply.xp, 0)) then return false end
    if not result.ok and reply.xp ~= nil and reply.xp ~= 0 then return false end
    for _, field in ipairs({"cash", "gold", "crates", "bonusCrates"}) do
        if reply[field] ~= nil and reply[field] ~= reward[field] then return false end
    end
    for _, field in ipairs({"crateId", "bonusCrateId"}) do
        if reply[field] ~= nil and reply[field] ~= result[field] then return false end
    end
    return true
end
local function reconcile(proposal, before, after, reply, baseline, restart, completedReceipt)
    local intent = type(proposal) == "table" and proposal.intent
    if not validIntent(intent) or type(baseline) ~= "table" or type(baseline.result) ~= "table"
        or type(baseline.rewards) ~= "table" or type(baseline.projection) ~= "table"
        or type(before) ~= "table" or type(after) ~= "table" or type(reply) ~= "table"
        or not same(proposal, before) or not same(proposal, baseline) or not same(proposal, after, restart)
        or before.revision ~= baseline.revision or proposal.revision ~= baseline.revision
        or intent.sequence ~= baseline.sequence or intent.resultKey ~= baseline.resultKey
        or reply.pending == true or reply.code == "pending" or reply.code == "no_pending"
        or reply.code == "rate_limited" or reply.code == "presence" or reply.code == "busy" then return "pending" end
    local native, board, protocol, proof = current(after)
    if not native or board.mine ~= nil or proof.sourceKey ~= baseline.boardSourceKey
        or native.serverNow < baseline.serverNow or board.serverNow < baseline.boardServerNow
        or (not completedReceipt and protocol.controllerCounter ~= baseline.sequence)
        or not (after.session == baseline.session and after.revision > baseline.revision
            and after.capturedAt >= baseline.capturedAt
            or restart and after.session ~= baseline.session and native.serverNow > baseline.serverNow) then return "pending" end
    -- A completed positive receipt already owns the original invocation. A
    -- different controller supplies only fresh replicated custody; its sequence
    -- is never adopted as authority for that historical action.
    if completedReceipt and protocol.nativeJob == baseline.nativeJob
        and protocol.nativeEpoch == baseline.nativeEpoch then return "pending" end
    for _, field in ipairs(scope) do
        if intent[field] ~= baseline[field]
            or (not completedReceipt or field == "nativeSourceKey") and protocol[field] ~= baseline[field] then return "pending" end
    end
    if reply.ok == false then
        return protocol.resultKey == baseline.resultKey and equal(copied(board.result), baseline.result)
            and custody(native, protocol, baseline, true) and "rejected" or "pending"
    end
    if reply.ok ~= true or board.result ~= nil or protocol.resultKey ~= nil
        or not terminalQuote(reply, baseline) then return "pending" end
    local savedProtocol = before.heistProtocolProof
    local awarded = baseline.result.ok and reply.xp or 0
    local thresholds = baseline.xpThresholds
        or type(savedProtocol) == "table" and savedProtocol.xpThresholds
        or baseline.projection.thresholds
    local projection = projectXP({level = baseline.level, xp = baseline.xp}, awarded, thresholds)
    if not projection then return "pending" end
    return custody(native, protocol, baseline, false, projection) and "confirmed" or "pending"
end

function HeistCollectEvidence.evaluate(proposal, before, after, reply, baseline)
    return reconcile(proposal, before, after, reply, baseline, false)
end
local function savedBaseline(data)
    if type(data) ~= "table" or type(data.reply) ~= "table" then return nil end
    local baseline = HeistCollectEvidence.capture(data.proposal, data.before)
    -- Older exact records retained the full protocol in before, but only the
    -- base-XP threshold subset in baseline. Validate their original shape;
    -- recovery can still use that saved protocol without rewriting history.
    if baseline and type(data.baseline) == "table" and data.baseline.xpThresholds == nil then
        baseline.xpThresholds = nil
    end
    return baseline and equal(baseline, data.baseline) and baseline or nil
end
function HeistCollectEvidence.recoverSaved(data, after)
    local baseline = savedBaseline(data)
    if not baseline then return nil end
    local result = reconcile(data.proposal, data.before, after, data.reply, baseline, true)
    return (result == "confirmed" or result == "rejected") and result or nil
end
function HeistCollectEvidence.recoverCompleted(data, after)
    local baseline = savedBaseline(data)
    if not baseline or baseline.result.ok ~= true or data.reply.ok ~= true or data.reply.collected ~= true then return nil end
    local result = reconcile(data.proposal, data.before, after, data.reply, baseline, true, true)
    return result == "confirmed" and result or nil
end
function HeistCollectEvidence.canDispatch(proposal, raw)
    return HeistCollectEvidence.capture(proposal, raw) ~= nil
end
return HeistCollectEvidence
