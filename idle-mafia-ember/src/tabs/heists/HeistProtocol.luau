-- One source-owned sequence lane for all four Heist mutations. Status never replays.
local HeistProtocol = {}
local Methods = {}
Methods.__index = Methods
local features = {heists = "heistStart", heistCollect = "heistCollect", favors = "favorHelp", sabotage = "heistSabotage"}
local commands = {heistStart = "start", heistCollect = "collect", favorHelp = "help", heistSabotage = "sabotage"}
local headers = {"session", "account", "place", "release", "revision", "capturedAt"}
local function copy(raw) local out = {}; for key, value in pairs(raw) do out[key] = value end; return out end
local function integer(value, low)
    return type(value) == "number" and value == value and value >= low and value <= 9007199254740991 and value % 1 == 0
end
local function same(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not same(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function proof(raw)
    local value = type(raw) == "table" and raw.heistProtocolProof
    if type(value) ~= "table" then return nil end
    for _, key in ipairs(headers) do if value[key] ~= raw[key] then return nil end end
    return value
end
local function terminal(reply)
    return type(reply) == "table" and type(reply.ok) == "boolean" and reply.pending ~= true
        and reply.code ~= "pending" and reply.code ~= "no_pending" and reply.code ~= "rate_limited"
        and reply.code ~= "presence" and reply.code ~= "busy"
end
local function call(proposal, status)
    local intent = type(proposal) == "table" and proposal.intent
    if type(intent) ~= "table" or features[proposal.feature] ~= intent.kind or not integer(intent.sequence, 1) then return nil end
    local arg = intent.kind == "heistStart" and intent.heistId or intent.kind ~= "heistCollect" and intent.rowId or nil
    if intent.kind ~= "heistCollect" and not (type(arg) == "string" and #arg > 0 and #arg <= 120
        or integer(arg, 1)) then return nil end
    return {remote = "HeistAction", method = "InvokeServer", arity = 3,
        args = {status and "status" or commands[intent.kind], arg, intent.sequence},
        kind = status and "statusOnly" or "mutation", actionKey = proposal.actionKey}
end
local function matches(observed, intent)
    return type(observed) == "table" and type(intent) == "table"
        and observed.nativeJob == intent.nativeJob and observed.nativeEpoch == intent.nativeEpoch
        and observed.nativeSourceKey == intent.nativeSourceKey and integer(intent.sequence, 1)
        and observed.controllerCounter >= intent.sequence - 1
end
-- Complete bounded result payload, including unknown fields, gives collect's
-- nil target a local identity. It is not a server run identifier.
local function canonical(raw)
    local seen, nodes = {}, 0
    local function encode(value, depth)
        nodes = nodes + 1
        if nodes > 2048 or depth > 8 then error("Heist result too large") end
        local kind = type(value)
        if kind == "boolean" then return value and "b1" or "b0" end
        if kind == "number" then
            local numeric = tonumber(value)
            assert(numeric and numeric == numeric and math.abs(numeric) <= 9007199254740991, "Invalid result number")
            return "n" .. string.format("%.17g", numeric)
        end
        if kind == "string" then assert(#value <= 16384, "Result text too large"); return "s" .. #value .. ":" .. value end
        assert(kind == "table" and not seen[value] and getmetatable(value) == nil, "Invalid result payload")
        seen[value] = true
        local rows = {}
        for key, child in pairs(value) do
            assert(type(key) == "string" or type(key) == "number", "Invalid result key")
            rows[#rows + 1] = {key = encode(key, depth + 1), value = encode(child, depth + 1)}
        end
        table.sort(rows, function(a, b) return a.key < b.key end)
        local out = {"t" .. #rows .. ":"}
        for _, row in ipairs(rows) do out[#out + 1] = #row.key .. ":" .. row.key .. #row.value .. ":" .. row.value end
        seen[value] = nil
        return table.concat(out)
    end
    return encode(raw, 1)
end
function HeistProtocol.new(deps)
    assert(type(deps) == "table" and type(deps.lease) == "table" and type(deps.lease.Quote) == "function"
        and type(deps.lease.Observe) == "function" and type(deps.clock) == "table"
        and type(deps.clock.Now) == "function" and type(deps.identity) == "table", "Missing owned Heist protocol")
    return setmetatable({lease = deps.lease, clock = deps.clock, identity = deps.identity,
        hash = deps.hash, config = deps.config, xpFunction = type(deps.config) == "table" and deps.config.xpForLevel,
        closed = false}, Methods)
end
function Methods:BindCheckpoint(checkpoint)
    assert(not self.checkpoint or self.checkpoint == checkpoint, "Heist checkpoint already bound")
    self.checkpoint = checkpoint
end
function Methods:Unresolved()
    if not self.checkpoint or self.checkpoint.fault then return true end
    for _, record in ipairs(self.checkpoint:Records()) do if features[record.feature] then return true end end
    return false
end
function Methods:Enrich(raw)
    local out = copy(raw)
    out.heistProtocolProof = nil
    if self.closed or raw.account ~= self.identity.account or raw.place ~= self.identity.place
        or raw.release ~= self.identity.release or type(raw.native) ~= "table" or raw.native.fullSync ~= true then return out end
    local observed = self.lease:Observe()
    if not observed then return out end
    local owned = copy(observed)
    for _, key in ipairs(headers) do owned[key] = raw[key] end
    if not self:Unresolved() then owned.quote = self.lease:Quote() end
    local board = type(raw.heistBoardProof) == "table" and raw.heistBoardProof.board
    if type(board) == "table" and type(board.result) == "table" and type(self.hash) == "function" then
        local encoded, bytes = pcall(canonical, board.result)
        local ok, digest = false, nil
        if encoded then ok, digest = pcall(self.hash, bytes) end
        if ok and type(digest) == "string" and #digest == 64 and digest:match("^[0-9a-f]+$") then owned.resultKey = digest end
    end
    do
        local level = raw.native.level
        if integer(level, 1) and type(self.xpFunction) == "function" and self.config.xpForLevel == self.xpFunction then
            if not self.xpCache or self.xpCache.level ~= level then
                local values = {}
                for current = level, level + 128 do
                    local valid, needed = pcall(self.xpFunction, current)
                    if not valid or not integer(needed, 1) then break end
                    values[current] = needed
                end
                self.xpCache = {level = level, values = values}
            end
            owned.xpThresholds = copy(self.xpCache.values)
        end
    end
    out.heistProtocolProof = owned
    return out
end
function Methods:Release(proposal)
    if type(proposal) ~= "table" or not features[proposal.feature] then return false end
    local released, why, category = self.lease:Release(proposal)
    if released or category == "absent" then
        if self.active and self.active.proposal == proposal then
            -- The adapter releases native flags before its definitely-uninvoked
            -- callback. Keep only that exact preparation for the append-only fact.
            self.releasedPreparation = self.active.deliver == nil and self.active or nil
            self.active = nil
        end
        return true, nil
    end
    return false, why
end
function Methods:Returned(proposal, reply, deliver)
    local active = self.active
    if self.closed or not active or active.proposal ~= proposal or not self.lease:Owns(proposal) then return false end
    if type(deliver) == "function" and active.deliver == nil then active.deliver = deliver end
    if active.terminal ~= nil or not terminal(reply) or type(active.deliver) ~= "function" then return true end
    active.terminal = reply -- Fence duplicate/reentrant statuses before persistence can yield.
    active.deliver(reply)
    return true
end
function Methods:StatusCall()
    if self.closed then return nil, "Heist protocol closed" end
    local observed = self.lease:Observe()
    if not observed then return nil, "Original native Heist controller unavailable" end
    local active = self.active
    if active then
        if active.terminal == nil and active.deliver and self.lease:Owns(active.proposal) then
            return call(active.proposal, true), nil
        end
        return nil, "Initial Heist invocation or terminal custody still owned"
    end
    if self.checkpoint and not self.checkpoint.fault then
        for _, record in ipairs(self.checkpoint:Records()) do
            if features[record.feature] then
                local data = self.checkpoint:Recovery(record.actionKey)
                local p = data and data.proposal
                if data and data.reply == nil and p and p.account == self.identity.account and p.place == self.identity.place
                    and p.release == self.identity.release and matches(observed, p.intent)
                    and not self.checkpoint:KnownUnsent(record) then return call(p, true), nil end
            end
        end
    end
    return nil, "No same-controller Heist status pending"
end
function Methods:AcceptStatus(request, reply)
    if self.closed or type(request) ~= "table" or request.kind ~= "statusOnly" or not terminal(reply) then return true end
    local expected = self:StatusCall()
    if not expected or not same(expected, request) then return false end
    if self.active and self.active.proposal.actionKey == request.actionKey then
        return self:Returned(self.active.proposal, reply)
    end
    return self.checkpoint:RecordReply(request.actionKey, reply)
end
function Methods:Wrap(spec)
    local owner, result = self, copy(spec)
    result.reader = {read = function(raw, context)
        local view, reason = spec.reader.read(raw, context)
        if not view then return nil, reason end
        view = copy(view)
        view.protocol = proof(raw)
        local board = type(raw.heistBoardProof) == "table" and raw.heistBoardProof.board
        if spec.id == "heistCollect" and type(board) == "table" then
            view.result, view.resultKey = board.result, view.protocol and view.protocol.resultKey
            view.resultAddressable = view.resultKey ~= nil
        end
        return view, nil
    end}
    result.planner = {propose = function(view, settings, reservations)
        local p, reason = spec.planner.propose(view, settings, reservations)
        if not p then return nil, reason end
        local quote = type(view.protocol) == "table" and view.protocol.quote
        if type(quote) ~= "table" then return nil, "Current native Heist sequence unavailable or unresolved" end
        for _, key in ipairs({"sequence", "nativeJob", "nativeEpoch", "nativeSourceKey"}) do p.intent[key] = quote[key] end
        p.intent.needsSequence = true
        return p, nil
    end}
    result.canDispatch = function(p)
        return not owner.closed and owner.lease:Owns(p) and (not spec.canDispatch or spec.canDispatch(p) == true)
    end
    result.lifecycle = {
        prepare = function(p, raw, baseline, at)
            if owner.closed or owner:Unresolved() then return false, "Shared Heist protocol has an unresolved action", "controller_wait" end
            local acquired, why = owner.lease:Acquire(p, at + 45)
            if not acquired then return false, why, "controller_wait" end
            owner.releasedPreparation = nil
            owner.active = {proposal = p, before = raw, baseline = baseline}
            return true, nil
        end,
        authorize = function(p)
            if not owner.closed and owner.lease:Owns(p) then return call(p, false) end
            return nil
        end,
        returned = function(p, reply)
            return owner.active ~= nil and owner.active.proposal == p and owner.active.terminal == reply
        end,
        resolve = function(p) return owner:Release(p) end,
        unsent = function(p) return owner:Release(p) end,
        abandonedUnsent = function(p)
            local prepared = owner.active or owner.releasedPreparation
            if not prepared or prepared.proposal ~= p or prepared.deliver ~= nil
                or not owner.checkpoint then return false end
            local saved = owner.checkpoint:RecordUnsent(p, prepared.before, prepared.baseline)
            if saved and owner.releasedPreparation == prepared then owner.releasedPreparation = nil end
            return saved
        end,
    }
    result.recoverSaved = function(data, after)
        if owner.closed or not owner.checkpoint or type(data) ~= "table" or type(data.proposal) ~= "table" then return nil end
        local p = data.proposal
        if p.feature ~= spec.id or p.account ~= owner.identity.account or p.place ~= owner.identity.place
            or p.release ~= owner.identity.release or type(after) ~= "table"
            or after.account ~= p.account or after.place ~= p.place or after.release ~= p.release then return nil end
        -- An exact adapter receipt proves no invocation began. It survives a
        -- server/controller change without adopting that controller's counter.
        for _, record in ipairs(owner.checkpoint:Records()) do
            if record.actionKey == p.actionKey and owner.checkpoint:KnownUnsent(record) then return "known_unsent" end
        end
        if not matches(proof(after), p.intent) then
            if spec.id == "heistCollect" and type(spec.evidence.recoverCompleted) == "function" then
                return spec.evidence.recoverCompleted(data, after)
            end
            return nil
        end
        if type(spec.evidence.recoverSaved) == "function" then return spec.evidence.recoverSaved(data, after) end
        if not terminal(data.reply) then return nil end
        local baseline = spec.evidence.capture(p, data.before)
        if not baseline or not same(baseline, data.baseline) then return nil end
        local status = spec.evidence.evaluate(p, data.before, after, data.reply, data.baseline)
        return (status == "confirmed" or status == "rejected") and status or nil
    end
    return result
end
function Methods:Close()
    if self.closed then return end
    self.closed = true
    if self.active then self:Release(self.active.proposal) end
    self.lease:Close()
end
return HeistProtocol
