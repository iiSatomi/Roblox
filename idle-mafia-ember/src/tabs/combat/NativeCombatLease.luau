-- Conditional native/manual ownership. Expiry releases a local guard, not an RPC.
local NativeCombatLease = {}
local Methods = {}
Methods.__index = Methods
local MAX = 9007199254740991
local scopes = {"session", "account", "place", "release"}
local kinds = {playerAttack = "Attack", playerScout = "ScoutPlayer"}
local function finite(value)
    return type(value) == "number" and value == value and value >= 0 and value <= MAX
end
local function integer(value, minimum) return finite(value) and value % 1 == 0 and value >= minimum end
local function text(value) return type(value) == "string" and #value > 0 and #value <= 1000 end
local function time(self)
    local ok, value = pcall(self.clock.Now, self.clock)
    return ok and finite(value) and value or nil
end
local function snapshot(self)
    local ok, state = pcall(self.port.Read, self.port)
    if not ok or type(state) ~= "table" or not integer(state.scoutGeneration, 0)
        or state.scoutTarget ~= nil and not integer(state.scoutTarget, 1)
        or type(state.scoutBusy) ~= "boolean" or type(state.confirmationPending) ~= "boolean"
        or type(state.modalOpen) ~= "boolean" then return nil end
    return state
end
local function matches(self, proposal)
    if type(proposal) ~= "table" or not text(proposal.actionKey)
        or (proposal.feature ~= "combat" and proposal.feature ~= "warCombat")
        or type(proposal.intent) ~= "table" or not kinds[proposal.intent.kind]
        or not integer(proposal.intent.target, 1) then return false end
    for _, key in ipairs(scopes) do if proposal[key] ~= self.identity[key] then return false end end
    return true
end
local function expire(self)
    local current = time(self)
    if self.active and (not current or current >= self.active.deadline) then self:Release(self.active.proposal) end
    return current
end
local function current(self)
    if self.closed then return false end
    local ok, valid = pcall(self.port.Current, self.port)
    if not ok or valid ~= true then
        self.reason = "Native Combat source changed; owner retired"
        self:Close()
        return false
    end
    return true
end
local function compactNative(calls)
    while calls.head and calls.head.done do
        calls.head = calls.head.next
        calls.retained = calls.retained - 1
    end
    if not calls.head then calls.tail = nil end
end
local function nativeBusy(epoch)
    local calls = epoch.nativeCalls
    if not calls then return false end
    compactNative(calls)
    return calls.unknown == true or calls.head ~= nil
end
local function nativeCall(self, invoke, ...)
    local calls = self.epoch.nativeCalls
    if not calls then calls = {retained = 0}; self.epoch.nativeCalls = calls end
    compactNative(calls)
    local marker
    if calls.retained < 128 then
        marker = {done = false}
        if calls.tail then calls.tail.next = marker else calls.head = marker end
        calls.tail = marker
        calls.retained = calls.retained + 1
    else
        -- Preserve native behavior even at capacity. Further hub admission is
        -- unknown until a fresh controller; never drop a native RPC to track it.
        calls.unknown = true
        self.reason = "Native Combat activity exceeds retained tracking; quiescence unknown"
    end
    local result = table.pack(pcall(invoke, ...))
    if marker then marker.done = true; compactNative(calls) end
    if not result[1] then error(result[2], 0) end
    return table.unpack(result, 2, result.n)
end
local function physical(self, marker, invoke, ...)
    self.epoch.physical = marker
    local result = table.pack(pcall(invoke, ...))
    if self.epoch.physical == marker then self.epoch.physical = nil else marker.replaced = true end
    if self.permit and self.permit.marker == marker then self.permit = nil end
    if not result[1] then error(result[2], 0) end
    return table.unpack(result, 2, result.n)
end

function NativeCombatLease.new(port, clock, identity, epoch)
    if type(port) ~= "table" or port.nonYielding ~= true or type(port.Current) ~= "function"
        or type(port.Read) ~= "function" or type(port.CompareAttackBusy) ~= "function"
        or type(port.Install) ~= "function" or type(port.Restore) ~= "function"
        or type(clock) ~= "table" or type(clock.Now) ~= "function"
        or type(identity) ~= "table" or type(epoch) ~= "table" then
        return nil, "Non-yielding native Combat capabilities unavailable"
    end
    local own = {}
    for _, key in ipairs(scopes) do
        if not text(identity[key]) then return nil, "Native Combat scope unavailable" end
        own[key] = identity[key]
    end
    if epoch.binding or epoch.physical or nativeBusy(epoch) then return nil, "Previous native Combat ownership remains unresolved" end
    local self = setmetatable({port = port, clock = clock, identity = own, epoch = epoch, closed = false}, Methods)
    if not current(self) then return nil, self.reason end
    local state = snapshot(self)
    -- Source-owned generation starts at zero and only open increments it. The
    -- native open function can reset busy during an older Scout invocation.
    if not state or state.attackBusy ~= false or state.scoutBusy ~= false
        or state.scoutGeneration ~= 0 or state.scoutTarget ~= nil then
        return nil, "Pristine native Scout/Attack initialization cannot be established"
    end
    epoch.binding = self
    local ok, gate = pcall(port.Install, port, function(remote, forward, ...)
        expire(self)
        if (remote ~= "Attack" and remote ~= "ScoutPlayer") or not current(self) then return nil end
        local permit = self.permit
        if permit and not permit.used and permit.thread == coroutine.running() and permit.remote == remote
            and select("#", ...) == 1 and select(1, ...) == permit.target
            and epoch.physical == permit.marker and self:Owns(permit.proposal) then
            permit.used = true -- Exact one-use authorization before the RPC can yield.
            return forward(...)
        end
        if self.active or epoch.physical then return nil end
        return nativeCall(self, forward, ...)
    end)
    if not ok or gate == nil then
        epoch.binding = nil
        return nil, "Native Combat gateways could not be installed"
    end
    self.gate = gate
    return self, nil
end

function Methods:Acquire(proposal, deadline)
    local at = expire(self)
    if not current(self) or not at or not finite(deadline) or deadline <= at or deadline > at + 45
        or not matches(self, proposal) then return false, "Native Combat scope or deadline changed" end
    local state = snapshot(self)
    if self.active or self.epoch.physical or nativeBusy(self.epoch) or self.epoch.binding ~= self or not state
        or state.attackBusy ~= false or state.scoutBusy ~= false or state.confirmationPending or state.modalOpen then
        return false, "Native Combat or a manual confirmation owns the controller"
    end
    local token = {}
    self.active = {proposal = proposal, token = token, deadline = deadline,
        actionKey = proposal.actionKey, feature = proposal.feature, kind = proposal.intent.kind, target = proposal.intent.target}
    local ok, acquired = pcall(self.port.CompareAttackBusy, self.port, false, token)
    if not ok or acquired ~= true then
        self:Release(proposal)
        return false, "Native Combat guard contention"
    end
    return true, nil
end

function Methods:Owns(proposal)
    local at = expire(self)
    if not current(self) or not at then return false end
    local active, state = self.active, snapshot(self)
    if active and state and state.attackBusy ~= active.token then
        self.reason = "Native Combat guard identity changed"
        self:Close()
        return false
    end
    return active ~= nil and active.proposal == proposal and self.epoch.binding == self
        and matches(self, proposal) and active.actionKey == proposal.actionKey and active.feature == proposal.feature
        and active.kind == proposal.intent.kind and active.target == proposal.intent.target
        and state ~= nil and state.attackBusy == active.token
end

function Methods:Invoke(proposal, invoke, ...)
    if type(invoke) ~= "function" or not self:Owns(proposal) or self.epoch.physical or nativeBusy(self.epoch) then
        return false, "Exact native Combat invocation ownership required"
    end
    local state = snapshot(self)
    if not state or state.confirmationPending or state.modalOpen then
        return false, "Complete the native manual dialog before Combat can run"
    end
    local marker = {owner = self, proposal = proposal, remote = kinds[proposal.intent.kind]}
    self.permit = {marker = marker, thread = coroutine.running(), remote = marker.remote,
        target = proposal.intent.target, proposal = proposal, used = false}
    local result = table.pack(physical(self, marker, invoke, ...))
    if marker.replaced or not self:Owns(proposal) then return false, "Native Combat invocation owner changed before return" end
    return table.unpack(result, 1, result.n)
end

function Methods:Release(proposal)
    local active = self.active
    if not active or active.proposal ~= proposal then return false, "No owned native Combat guard" end
    -- The captured port remains the cleanup authority after broader source
    -- retirement. Only this exact opaque value may be restored to false.
    local ok, released = pcall(self.port.CompareAttackBusy, self.port, active.token, false)
    if not ok or released ~= true then
        local readOk, state = pcall(self.port.Read, self.port)
        local known = readOk and type(state) == "table"
            and (type(state.attackBusy) == "boolean" or type(state.attackBusy) == "table")
        if not known or state.attackBusy == active.token then
            self.reason = "Native Combat cleanup unconfirmed; exact guard custody retained"
            return false, self.reason
        end
    end
    self.active = nil
    if not self.closed then self.reason = nil end
    if self.closed and not self.gate and self.epoch.binding == self then self.epoch.binding = nil end
    return ok and released == true, released ~= true and "Native Combat guard is no longer owned" or nil
end

function Methods:Status()
    expire(self)
    current(self)
    return {closed = self.closed, active = self.active ~= nil,
        physical = self.epoch.physical ~= nil or nativeBusy(self.epoch), reason = self.reason}
end

function Methods:Close()
    if self.closed and not self.active and not self.gate then
        if self.epoch.binding == self then self.epoch.binding = nil end
        return true
    end
    self.closed = true
    self.permit = nil
    if self.active then self:Release(self.active.proposal) end
    if self.gate then
        local ok, restored = pcall(self.port.Restore, self.port, self.gate)
        if ok and restored == true then self.gate = nil
        else self.reason = "Native Combat gateway cleanup unconfirmed; exact proxy custody retained" end
    end
    local complete = not self.active and not self.gate
    if complete and self.epoch.binding == self then self.epoch.binding = nil end
    return complete
end

-- The two full module hashes were checked on the reviewed 653 client. Its
-- Scout generation's only writer is open's increment from the initial zero;
-- both current function fragments and all identifier uses were compared.
local FIGHT_SOURCE = "c8999f2c92e903f6901ac22c6c5752a7993b04451faed081fda22d3daac7c9af"
local PROFILE_SOURCE = "8329c1cff26a0cbd08e6aff6ef5919dded98e8fc9b69c189c7b5e98271a0475d"
local REGISTRY = "__IDLE_MAFIA_EMBER_COMBAT_OWNER_V1"
-- Run before NativeClientBindings captures wrappers for a new chunk. This has
-- no authority to close an active owner, invoke a remote or change a challenge.
function NativeCombatLease.cleanup(registry)
    if type(registry) ~= "table" then return false, "Native Combat ownership registry unavailable" end
    local epoch = rawget(registry, REGISTRY)
    if epoch == nil then return true, nil end
    if type(epoch) ~= "table" then return false, "Native Combat ownership record is ambiguous" end
    local owner = epoch.binding
    if owner == nil then return true, nil end
    if type(owner) ~= "table" or owner.closed ~= true or type(owner.Close) ~= "function" then
        return false, "Previous native Combat owner remains active or ambiguous"
    end
    local ok, complete = pcall(owner.Close, owner)
    if rawget(registry, REGISTRY) ~= epoch then return false, "Native Combat cleanup owner changed" end
    if not ok or complete ~= true or epoch.binding ~= nil then
        return false, ok and (owner.reason or "Native Combat exact cleanup remains unconfirmed") or "Native Combat exact cleanup raised"
    end
    return true, nil
end
local function primitives(readValues, writeValue, isC)
    if type(readValues) ~= "function" or type(writeValue) ~= "function" or type(isC) ~= "function"
        or not isC(readValues) or not isC(writeValue) then return false end
    local cell = false
    local function dummy(value, write) if write then cell = value end; return cell end
    local marker = {}
    local thread = coroutine.create(function()
        if type(readValues(dummy)) ~= "table" then return false end
        for _, value in ipairs({marker, false}) do
            writeValue(dummy, 1, value)
            if dummy() ~= value or readValues(dummy)[1] ~= value then return false end
        end
        return true
    end)
    local ok, valid = coroutine.resume(thread)
    return ok and valid == true and coroutine.status(thread) == "dead"
end

function NativeCombatLease.bind(deps)
    if type(deps) ~= "table" or type(deps.source) ~= "table" or type(deps.source.CombatController) ~= "function"
        or type(deps.env) ~= "table" or type(deps.registry) ~= "table" then
        return nil, "Native Combat binding capabilities unavailable"
    end
    local env = deps.env
    local readValues, writeValue = env.getupvalues, env.setupvalue
    if type(env.decompile) ~= "function" or type(env.crypt) ~= "table" or type(env.crypt.hash) ~= "function"
        or not primitives(readValues, writeValue, env.iscclosure) then
        return nil, "Non-yielding native Combat primitives unavailable"
    end
    local ok, owner, reason = pcall(function()
        local cleaned, cleanupReason = NativeCombatLease.cleanup(deps.registry)
        if not cleaned then return nil, cleanupReason end
        local controller, why = deps.source:CombatController()
        if not controller then return nil, why end
        if controller.readValues ~= readValues then return nil, "Native Combat primitive reader changed" end
        if type(deps.identity) ~= "table" or controller.account ~= deps.identity.account
            or controller.place ~= deps.identity.place then return nil, "Native Combat identity changed" end
        for _, row in ipairs({{controller.fightModule, FIGHT_SOURCE}, {controller.profileModule, PROFILE_SOURCE}}) do
            local bytes = env.decompile(row[1])
            if type(bytes) ~= "string" or env.crypt.hash(bytes, "sha256"):lower() ~= row[2] then
                return nil, "Unreviewed native Combat source"
            end
        end
        if controller:Current() ~= true then return nil, "Native Combat source changed during inspection" end
        local nativeRemotes, gate = controller.remotes, nil
        local originalAttack, originalScout = controller.attack, controller.scout
        local attackInvoke, scoutInvoke = originalAttack.InvokeServer, originalScout.InvokeServer
        local port = {nonYielding = true}
        function port:Current()
            return controller:Current() == true and originalAttack.InvokeServer == attackInvoke
                and originalScout.InvokeServer == scoutInvoke
                and nativeRemotes.Attack == (gate and gate.attack or originalAttack)
                and nativeRemotes.ScoutPlayer == (gate and gate.scout or originalScout)
                and (not gate or gate.attack.InvokeServer == gate.attackCall and gate.scout.InvokeServer == gate.scoutCall)
        end
        function port:Read()
            local attack = readValues(controller.attackBlocked)
            local profile = readValues(controller.profileOpen)
            local confirmation = readValues(controller.confirm)
            local visible, count = false, 0
            for _, child in ipairs(controller.modals:GetChildren()) do
                count = count + 1
                if count > 128 then error("Native modal collection changed") end
                if child:IsA("GuiObject") and child.Name ~= "Backdrop" and child.Visible then visible = true end
            end
            return {attackBusy = attack[1], scoutGeneration = profile[1], scoutTarget = profile[2], scoutBusy = profile[3],
                confirmationPending = confirmation[3] ~= nil, modalOpen = visible}
        end
        function port:CompareAttackBusy(expected, replacement)
            if readValues(controller.attackBlocked)[1] ~= expected then return false end
            writeValue(controller.attackBlocked, 1, replacement)
            return readValues(controller.attackBlocked)[1] == replacement
        end
        function port:Install(gateway)
            if gate then return nil end
            local nextGate = {attackRaw = rawget(nativeRemotes, "Attack"), scoutRaw = rawget(nativeRemotes, "ScoutPlayer")}
            nextGate.attackCall = function(_, ...)
                return gateway("Attack", function(...) return attackInvoke(originalAttack, ...) end, ...)
            end
            nextGate.scoutCall = function(_, ...)
                return gateway("ScoutPlayer", function(...) return scoutInvoke(originalScout, ...) end, ...)
            end
            nextGate.attack = {Name = originalAttack.Name, Instance = originalAttack.Instance, InvokeServer = nextGate.attackCall}
            nextGate.scout = {Name = originalScout.Name, Instance = originalScout.Instance, InvokeServer = nextGate.scoutCall}
            gate = nextGate
            local installed = pcall(function()
                rawset(nativeRemotes, "Attack", nextGate.attack)
                rawset(nativeRemotes, "ScoutPlayer", nextGate.scout)
                nextGate.registration = controller:RegisterGateways(nextGate.attack, nextGate.scout, function() return port:Current() end)
                assert(nextGate.registration, "Native Combat gateway registration refused")
            end)
            if not installed then self:Restore(nextGate); return nil end
            return nextGate
        end
        function port:Restore(previous)
            if rawget(nativeRemotes, "Attack") == previous.attack then rawset(nativeRemotes, "Attack", previous.attackRaw) end
            if rawget(nativeRemotes, "ScoutPlayer") == previous.scout then rawset(nativeRemotes, "ScoutPlayer", previous.scoutRaw) end
            if previous.registration then controller:UnregisterGateways(previous.registration) end
            if gate == previous then gate = nil end
            return true
        end
        local epoch = rawget(deps.registry, REGISTRY)
        if type(epoch) ~= "table" or epoch.context ~= controller.context or epoch.jobId ~= controller.jobId then
            epoch = {context = controller.context, jobId = controller.jobId}
            rawset(deps.registry, REGISTRY, epoch)
        end
        return NativeCombatLease.new(port, deps.clock, deps.identity, epoch)
    end)
    if not ok then return nil, "Native Combat binding inspection failed" end
    return owner, reason
end

return NativeCombatLease
