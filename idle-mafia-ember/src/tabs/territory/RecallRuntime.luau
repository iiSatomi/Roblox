-- One selected OWN deployment. Uses broker scheduling and status reads; never native retries.
local Runtime = {}
local MAX = 9007199254740991
local headers = {"session", "account", "place", "release", "revision", "capturedAt"}
local function integer(value, low, high)
    return type(value) == "number" and value == value and value % 1 == 0 and value >= low and value <= high
end
local function copy(value) local out = {}; for k, v in pairs(value) do out[k] = v end; return out end
local function same(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not same(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end
local function sameProposal(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({"session", "account", "place", "release", "revision", "feature", "actionKey"}) do
        if a[field] ~= b[field] then return false end
    end
    return same(a.intent, b.intent) and same(a.resources, b.resources)
end
function Runtime.new(deps)
    local source = type(deps) == "table" and deps.nativeRecallController
    if type(deps) ~= "table" or (source ~= nil and (type(source) ~= "table"
        or type(source.Read) ~= "function" or type(source.Current) ~= "function"))
        or type(deps.RecallTransactions) ~= "table" or type(deps.Stationing) ~= "table"
        or type(deps.identity) ~= "table" or type(deps.config) ~= "table"
        or type(deps.config.TERRITORY) ~= "table" then return nil, "Current native Recall owner unavailable" end
    local scope = copy(deps.identity)
    scope.userId = deps.nativeUserId
    local owner, reason = deps.RecallTransactions.new(deps.storage, scope, {release = deps.release,
        recallCooldownSeconds = deps.config.TERRITORY.recallCooldownSeconds})
    if not owner then return nil, reason end
    local readNative, currentNative = source and source.Read, source and source.Current
    local closed, latest, authorizedRequest = false, nil, nil
    local result = {owner = owner}
    local function native()
        if closed or not source or source.Read ~= readNative or source.Current ~= currentNative then return nil end
        local ok, current = pcall(currentNative)
        if not ok or current ~= true then return nil end
        local readOK, value = pcall(readNative)
        if not readOK or type(value) ~= "table" or not integer(value.lastRequestId, 0, MAX - 1)
            or not integer(value.epochFloor, 1, MAX - 1) or value.controllersClear ~= true
            or value.userId ~= scope.userId then return nil end
        return value
    end
    local function matched(proposal, record)
        local call = deps.RecallTransactions.describe(proposal)
        return record and call and proposal.actionKey == record.actionKey
            and proposal.intent.requestId == record.requestId and same(call.args[3][1], record.target)
            and proposal.account == record.account and proposal.place == record.place and proposal.release == record.release
            and proposal.session == record.baseline.session and proposal.revision == record.baseline.revision
    end
    local function plan(view, settings, requestId)
        if type(settings) ~= "table" or settings.enabled ~= true then return nil, "Crew deployment disabled" end
        if type(view) ~= "table" or type(view.raw) ~= "table" or type(view.reserved) ~= "table"
            or not integer(view.attempted, 0, 1000) or not integer(settings.maxAttempts, 0, 1000)
            or view.attempted >= settings.maxAttempts or not integer(settings.memberSlot, 2, 46)
            or not integer(settings.minGarrison, 0, 1000000) or settings.districtId ~= view.districtId
            or view.stationUnknown then return nil, "Selected Recall identity, defense reserve and attempt limit required" end
        local member = view.members[settings.memberSlot]
        local row = view.raw.native.crew[settings.memberSlot]
        if not member or member.duty ~= view.districtId or member.training or member.rolling or member.recalling
            or member.injured > view.serverNow or member.recalled > view.serverNow or view.reserved[member.key]
            or view.occupied - 1 < settings.minGarrison then return nil, "Selected deployment is reserved, unavailable or needed for defense" end
        if not requestId then
            local value = native()
            if owner:Active() or not value then return nil, "Native Recall queue or durable request still owned" end
            requestId = math.max(owner:LastRequestId() + 1, value.lastRequestId + 1, value.epochFloor)
        end
        local proposal = {feature = "station", actionKey = "recall:" .. view.districtId .. ":" .. member.key .. ":" .. tostring(requestId),
            resources = {}, intent = {kind = "territoryRecall", requestId = requestId, districtId = view.districtId,
                userId = scope.userId, memberIndex = settings.memberSlot, memberName = member.name, rarity = member.rarity,
                deploymentId = row.dutyToken, at = row.dutyAt, memberKey = member.key, familyId = view.familyId,
                districtRevision = view.districtRevision, sourceKey = view.sourceKey, minGarrison = settings.minGarrison,
                maxAttempts = settings.maxAttempts, attemptedBefore = view.attempted}}
        for _, field in ipairs({"session", "account", "place", "release", "revision"}) do proposal[field] = view[field] end
        if not deps.RecallTransactions.capture(proposal, view.raw, scope) then return nil, "Exact own deployment token and stable roster required" end
        return proposal, nil
    end
    local reader = {read = function(raw, context)
        local view, why = deps.Stationing.read(raw, context)
        if view then view.raw = raw end
        return view, why
    end}
    local function capture(proposal, before)
        local intent = type(proposal) == "table" and proposal.intent
        if type(intent) ~= "table" or intent.kind ~= "territoryRecall" then return nil, "Recall intent required" end
        local view = reader.read(before, before)
        local planned = view and plan(view, {enabled = true, districtId = intent.districtId,
            memberSlot = intent.memberIndex, minGarrison = intent.minGarrison, maxAttempts = intent.maxAttempts}, intent.requestId)
        if not sameProposal(planned, proposal) then return nil, "Recall source, limits or exact deployment changed" end
        local baseline = deps.RecallTransactions.capture(proposal, before, scope)
        if baseline then baseline.intent = copy(intent) end
        return baseline, baseline == nil and "Recall custody unavailable" or nil
    end
    local function recordMatches(proposal, baseline, record)
        return matched(proposal, record) and type(baseline) == "table"
            and same(baseline.target, record.target) and same(baseline.baseline, record.baseline)
            and same(baseline.intent, proposal.intent)
    end
    local function canDispatch(proposal)
        local active, value = owner:Active(), native()
        if not active or not (active.stage == "prepared" or active.stage == "sent"
                and authorizedRequest == active.requestId and not active.replyReceived)
            or not matched(proposal, active) or not value
            or value.lastRequestId >= active.requestId or type(latest) ~= "table" then return false end
        local raw = copy(latest)
        local proof = {members = {}, attempted = proposal.intent.attemptedBefore,
            pendingStation = {}, stationUnknown = false}
        for _, field in ipairs(headers) do proof[field] = raw[field] end
        raw.stationReservationProof = proof -- Broker independently checks every other custody holder at emission.
        return capture(proposal, raw) ~= nil
    end
    local function evaluate(proposal, _, after, _, baseline)
        local active = owner:Active()
        if not recordMatches(proposal, baseline, active) then return "pending" end
        local outcome = owner:Reconcile(after)
        return outcome == "observed" and "confirmed" or "pending"
    end
    local function recoverSaved(data, after)
        if closed or type(data) ~= "table" then return nil end
        local captured = capture(data.proposal, data.before)
        if not captured or not same(captured, data.baseline) then return nil end
        local receipt = owner:Receipt()
        if receipt and recordMatches(data.proposal, data.baseline, receipt.record) then return receipt.outcome end
        local active = owner:Active()
        if not recordMatches(data.proposal, data.baseline, active) then return nil end
        if active.stage == "prepared" then
            local recovered = owner:RecoverPrepared()
            return recovered and "known_unsent" or nil
        end
        if evaluate(data.proposal, data.before, after, data.reply, data.baseline) == "confirmed" then
            local cleared = owner:ClearObserved()
            return cleared and "confirmed" or nil
        end
        return nil
    end
    local lifecycle = {
        prepare = function(proposal, before, baseline, now)
            if proposal.intent.kind ~= "territoryRecall" then return true, nil end
            local value = native()
            if not value or value.lastRequestId >= proposal.intent.requestId
                or not same(capture(proposal, before), baseline) then return false, "Recall preflight changed" end
            return owner:Prepare(proposal, before, now)
        end,
        authorize = function(proposal, _, now)
            if proposal.intent.kind ~= "territoryRecall" then return deps.TerritoryCallPlan.describe(proposal) end
            if not canDispatch(proposal) then return nil, "Recall prepared custody or native queue changed" end
            local sent, why = owner:MarkSending(latest, now)
            if not sent then return nil, why end
            local call, whyCall = owner:SubmitCall(latest, now)
            if call then authorizedRequest = proposal.intent.requestId end
            return call, whyCall
        end,
        returned = function(proposal, reply)
            if proposal.intent.kind ~= "territoryRecall" then return true, nil end
            if closed or not matched(proposal, owner:Active()) then return false, "Recall return owner changed" end
            return owner:AcceptReply(proposal.intent.requestId, reply)
        end,
        resolve = function(proposal, outcome, after)
            if proposal.intent.kind ~= "territoryRecall" or outcome == "skipped_unconfirmed" then return true, nil end
            if outcome ~= "confirmed" or not matched(proposal, owner:Active())
                or owner:Reconcile(after) ~= "observed" then return false, "Exact observed Recall required" end
            return owner:ClearObserved()
        end,
        unsent = function(proposal)
            if proposal.intent.kind ~= "territoryRecall" then return true, nil end
            return owner:CancelUnsent(proposal.intent.requestId, proposal.actionKey)
        end,
    }
    lifecycle.abandonedUnsent, lifecycle.recover = lifecycle.unsent, recoverSaved
    function result:Enrich(raw)
        latest = raw
        local active = owner:Active()
        if active and active.stage == "prepared" then owner:RecoverPrepared() end
        return raw
    end
    function result:Feature(original)
        local spec = copy(original)
        spec.reader = reader
        spec.planner = {propose = function(view, settings, reservations)
            if settings.mode == "Recall" then return plan(view, settings) end
            if owner:Active() then return nil, "Own Recall still unresolved" end
            return deps.Stationing.propose(view, settings, reservations)
        end}
        spec.evidence = {
            capture = function(proposal, before)
                if proposal.intent.kind == "territoryRecall" then return capture(proposal, before) end
                return deps.Stationing.capture(proposal, before)
            end,
            evaluate = function(proposal, before, after, reply, baseline)
                if proposal.intent.kind == "territoryRecall" then return evaluate(proposal, before, after, reply, baseline) end
                return deps.Stationing.evaluate(proposal, before, after, reply, baseline)
            end,
        }
        spec.canDispatch = function(proposal)
            if closed then return false end
            if proposal.intent.kind == "territoryRecall" then return canDispatch(proposal) end
            return not owner:Active() and deps.Stationing.canDispatch(proposal, latest)
        end
        spec.recoverSaved = function(data, after)
            if data.proposal.intent.kind == "territoryRecall" then return recoverSaved(data, after) end
            return deps.Stationing.recoverSaved(data, after)
        end
        spec.lifecycle = lifecycle
        return spec
    end
    function result:ReadSources()
        return {{id = "recallStatus", interval = 3, confirmFeatures = {station = true},
            enabled = function() local active = owner:Active(); return not closed and active ~= nil and active.stage == "sent" end,
            prepare = function()
                if not native() then return nil, "Current idle native Recall controller required" end
                return owner:StatusCall()
            end,
            accept = function(_, request, reply)
                local active = owner:Active()
                if closed or not active or request.args[2] ~= active.requestId or request.actionKey ~= active.actionKey
                    or type(reply) ~= "table" or type(reply.ok) ~= "boolean" then return nil end
                return {requestId = active.requestId, actionKey = active.actionKey, reply = reply}
            end,
            commit = function(staged)
                local active = owner:Active()
                return not closed and active and staged.actionKey == active.actionKey
                    and owner:AcceptReply(staged.requestId, staged.reply) or false
            end,
        }}
    end
    function result:ReservationSources()
        return {{id = "territoryRecall", read = function()
            local active = owner:Active()
            if not active then return nil end
            local member = active.baseline.members[tostring(active.target.memberIndex)]
            return {account = scope.account, place = scope.place, release = scope.release, feature = "station", actionKey = active.actionKey,
                claims = {members = {[member.key] = true, ["slot:" .. active.target.memberIndex] = true},
                    funds = {}, items = {}, allCrew = false, allItems = false}}
        end}}
    end
    function result:Close() closed, latest = true, nil end
    return result, nil
end
return Runtime
