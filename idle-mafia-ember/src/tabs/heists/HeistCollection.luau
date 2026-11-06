-- The native collect call addresses the current personal result slot, without a server run-ID argument.
local Collection = {}
local MAX = 9007199254740991
local headers = {"session", "account", "place", "release", "revision", "capturedAt"}
local rewards = {"cash", "xp", "gold", "crates", "bonusCrates"}
local function number(value) return type(value) == "number" and value == value and value >= 0 and value <= MAX end
local function integer(value, low) return number(value) and value % 1 == 0 and value >= low end
local function text(value) return type(value) == "string" and #value > 0 and #value <= 200 and not value:find("[%c]") end
local function copy(value) local out = {}; for key, part in pairs(value) do out[key] = part end; return out end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function matching(a, b, fields)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs(fields) do if a[field] ~= b[field] then return false end end
    return true
end
function Collection.new(hash, fingerprint, release)
    assert(type(hash) == "function" and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$") and text(release), "Reviewed Heist collection source required")
    fingerprint = fingerprint:lower()
    local function signature(result, account)
        if type(result) ~= "table" or not text(result.heistId) or type(result.ok) ~= "boolean" then return nil end
        for _, field in ipairs(rewards) do if result[field] ~= nil and not integer(result[field], 0) then return nil end end
        if (result.crates or 0) > 0 and not text(result.crateId)
            or (result.bonusCrates or 0) > 0 and not text(result.bonusCrateId) then return nil end
        local keys, parts = {}, {fingerprint, release, account}
        for key, value in pairs(result) do
            if not text(key) or #keys >= 64 then return nil end
            local kind = type(value)
            if kind == "string" then if #value > 4096 then return nil end
            elseif kind == "number" then if value ~= value or math.abs(value) > MAX then return nil end
            elseif kind ~= "boolean" then return nil end
            keys[#keys + 1] = key
        end
        table.sort(keys)
        for _, key in ipairs(keys) do
            local value = result[key]
            local encoded = type(value) == "number" and string.format("%.17g", value) or tostring(value)
            parts[#parts + 1] = #key .. ":" .. key .. ":" .. type(value) .. ":" .. #encoded .. ":" .. encoded
        end
        local ok, value = pcall(hash, table.concat(parts, "|"))
        return ok and type(value) == "string" and #value == 64 and value:match("^[%x]+$") and value:lower() or nil
    end
    local function board(raw)
        local proof = type(raw) == "table" and raw.heistBoardProof
        local native = type(raw) == "table" and raw.native
        if type(native) ~= "table" or native.fullSync ~= true or not number(native.serverNow)
            or raw.release ~= release or raw.catalogKey ~= fingerprint or not integer(raw.revision, 0)
            or not number(raw.capturedAt) or type(proof) ~= "table" or proof.query ~= nil
            or proof.sourceKey ~= fingerprint or proof.account ~= raw.account or proof.capturedAt ~= raw.capturedAt
            or not matching(proof.header, raw, headers) or type(proof.board) ~= "table"
            or proof.board.ok ~= true or not number(proof.board.serverNow)
            or math.abs(proof.board.serverNow - native.serverNow) > 2 then return nil end
        for _, field in ipairs({"session", "account", "place", "release"}) do if not text(raw[field]) then return nil end end
        return proof.board
    end
    local result = {}
    result.read = function(raw, context)
        local current, proof = board(raw), type(raw) == "table" and raw.heistControllerProof
        if not matching(raw, context, headers) or not current or current.mine ~= nil
            or type(proof) ~= "table" or not matching(proof, raw, headers)
            or not integer(proof.sequence, 0) or proof.sequence >= MAX or proof.controllersClear ~= true then
            return nil, "Fresh personal result and clear native sequence ownership required"
        end
        local key = signature(current.result, raw.account)
        if not key then return nil, "Complete personal Heist result identity required" end
        local view = copy(raw)
        view.resultKey, view.resultHeistId, view.resultSummary = key, current.result.heistId, copy(current.result)
        view.controllerSequenceBefore, view.serverDay = proof.sequence, math.floor(current.serverNow / 86400)
        return view, nil
    end
    result.propose = function(view, settings)
        if type(settings) ~= "table" or settings.enabled ~= true then return nil, "Heist collection disabled" end
        if type(view) ~= "table" or not text(view.resultHeistId) or not integer(view.serverDay, 0)
            or not integer(view.controllerSequenceBefore, 0) or view.controllerSequenceBefore >= MAX
            or signature(view.resultSummary, view.account) ~= view.resultKey then return nil, "Current personal result identity required" end
        local proposal = {feature = "heistCollect", resources = {},
            actionKey = "heistCollect:" .. view.serverDay .. ":" .. view.controllerSequenceBefore .. ":" .. view.resultKey,
            intent = {kind = "heistCollect", resultKey = view.resultKey, heistId = view.resultHeistId,
                sourceKey = fingerprint, serverDay = view.serverDay,
                controllerSequenceBefore = view.controllerSequenceBefore, needsSequence = true}}
        for _, field in ipairs({"session", "account", "place", "release", "revision"}) do proposal[field] = view[field] end
        return proposal, nil
    end
    result.capture = function(proposal, before)
        local view = result.read(before, before)
        local planned = view and result.propose(view, {enabled = true})
        if not planned or not matching(proposal, planned, {"session", "account", "place", "release", "revision", "feature", "actionKey"})
            or not equal(proposal.intent, planned.intent) or not equal(proposal.resources, {}) then return nil, "Heist result, day or native counter changed" end
        local baseline = {resultKey = view.resultKey, resultSummary = copy(view.resultSummary), intent = copy(planned.intent)}
        for _, field in ipairs(headers) do baseline[field] = before[field] end
        return baseline, nil
    end
    local function evaluate(proposal, before, after, reply, baseline, recovery)
        if type(proposal) ~= "table" or type(before) ~= "table" or type(after) ~= "table" or type(baseline) ~= "table"
            or type(reply) ~= "table" or not matching(proposal, baseline, {"session", "account", "place", "release", "revision"})
            or not matching(before, baseline, headers) or not matching(after, baseline, {"account", "place", "release"})
            or proposal.feature ~= "heistCollect" or not equal(proposal.intent, baseline.intent)
            or not equal(proposal.resources, {}) or signature(baseline.resultSummary, baseline.account) ~= baseline.resultKey
            or proposal.intent.resultKey ~= baseline.resultKey or proposal.intent.sourceKey ~= fingerprint then return "pending" end
        if after.session == baseline.session then
            if not integer(after.revision, baseline.revision + 1) then return "pending" end
        elseif not recovery or not text(after.session) then return "pending" end
        local current = board(after)
        if not current or not number(before.native and before.native.serverNow)
            or after.native.serverNow < before.native.serverNow
            or math.floor(current.serverNow / 86400) ~= proposal.intent.serverDay
            or reply.pending == true or reply.code == "rate_limited" or reply.code == "busy"
            or reply.code == "presence" or reply.code == "no_pending" then return "pending" end
        if reply.ok == false then
            return signature(current.result, baseline.account) == baseline.resultKey and "rejected" or "pending"
        end
        if reply.ok ~= true or reply.collected ~= true or current.result ~= nil or current.mine ~= nil then return "pending" end
        for _, field in ipairs(rewards) do
            local expected = baseline.resultSummary[field] or 0
            if (reply[field] or 0) ~= expected or expected > 0 and reply[field] == nil then return "pending" end
        end
        for _, field in ipairs({"crateId", "bonusCrateId"}) do
            if baseline.resultSummary[field] ~= nil and reply[field] ~= baseline.resultSummary[field] then return "pending" end
        end
        return "confirmed"
    end
    result.evaluate = function(proposal, before, after, reply, baseline)
        return evaluate(proposal, before, after, reply, baseline, false)
    end
    result.recoverSaved = function(data, after)
        if type(data) ~= "table" then return nil end
        local captured = result.capture(data.proposal, data.before)
        if not captured or not equal(captured, data.baseline) then return nil end
        local outcome = evaluate(data.proposal, data.before, after, data.reply, captured, true)
        return (outcome == "confirmed" or outcome == "rejected") and outcome or nil
    end
    return result
end
return Collection
