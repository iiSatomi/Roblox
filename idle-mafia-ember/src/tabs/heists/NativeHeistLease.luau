-- Own the reviewed native Heist controller without starting its retry worker.
local NativeHeistLease = {}
local Methods = {}
Methods.__index = Methods
local actions = {heistStart = "start", heistCollect = "collect", favorHelp = "help", heistSabotage = "sabotage"}

local function integer(value, minimum)
    return type(value) == "number" and value == value and value % 1 == 0
        and value >= minimum and value <= 9007199254740991
end
local function text(value)
    return type(value) == "string" and #value > 0 and #value <= 120
end
local function now(self)
    local ok, value = pcall(self.clock.Now, self.clock)
    return ok and type(value) == "number" and value == value and value >= 0 and value or nil
end
local function read(self, current)
    if current then
        local ok, valid = pcall(self.port.Current, self.port)
        if not ok or valid ~= true then return nil, "Native Heist controller changed" end
    end
    local ok, state = pcall(self.port.Read, self.port)
    if not ok or type(state) ~= "table" or not integer(state.counter, 0)
        or type(state.running) ~= "boolean" then return nil, "Native Heist controller unavailable" end
    if current then
        if self.epoch.retired or state.counter < self.epoch.counterSeen then
            self.epoch.retired = true
            return nil, "Native Heist counter epoch retired"
        end
        self.epoch.counterSeen = state.counter
    end
    return state, nil
end
local function matches(self, proposal)
    local intent = type(proposal) == "table" and proposal.intent
    return type(intent) == "table" and actions[intent.kind] ~= nil
        and proposal.account == self.scope.account and proposal.place == self.scope.place
        and intent.nativeJob == self.scope.jobId and intent.nativeEpoch == self.epoch.id
        and intent.nativeSourceKey == self.scope.sourceKey and integer(intent.sequence, 1)
end
local function repaint(self)
    if type(self.port.Refresh) == "function" then pcall(self.port.Refresh, self.port) end
end

function NativeHeistLease.new(port, clock, scope, epoch)
    if type(port) ~= "table" or type(port.Current) ~= "function"
        or type(port.Read) ~= "function" or type(port.Write) ~= "function"
        or type(clock) ~= "table" or type(clock.Now) ~= "function"
        or type(scope) ~= "table" or not text(scope.account) or not text(scope.place)
        or not text(scope.jobId) or type(scope.sourceKey) ~= "string" or #scope.sourceKey ~= 64
        or type(epoch) ~= "table" or not text(epoch.id) or not integer(epoch.counterSeen, 0) then
        return nil, "Missing native Heist lease capabilities"
    end
    return setmetatable({port = port, clock = clock, scope = scope, epoch = epoch, closed = false}, Methods), nil
end

local function expireOwned(self)
    local live, time = self.epoch.live, now(self)
    if live and time and type(live.deadline) == "number" and time >= live.deadline
        and type(live.release) == "function" then pcall(live.release) end
end
function Methods:Observe()
    if self.closed then return nil, "Native Heist lease closed" end
    expireOwned(self)
    local state, reason = read(self, true)
    if not state then return nil, reason end
    return {controllerCounter = state.counter, nativeJob = self.scope.jobId,
        nativeEpoch = self.epoch.id, nativeSourceKey = self.scope.sourceKey}, nil
end

function Methods:Quote()
    if self.closed then return nil, "Native Heist lease closed" end
    -- A hard-stopped same-VM owner may leave its exact token. Release that token
    -- only after its original deadline; never adopt a native UI operation.
    expireOwned(self)
    local state, reason = read(self, true)
    if not state then return nil, reason end
    if state.pending ~= nil or state.running or state.inflight ~= nil or self.epoch.live ~= nil
        or state.counter >= 9007199254740991 then return nil, "Native Heist controller busy" end
    return {sequence = state.counter + 1, nativeJob = self.scope.jobId,
        nativeEpoch = self.epoch.id, nativeSourceKey = self.scope.sourceKey}, nil
end

function Methods:Acquire(proposal, deadline)
    local time = now(self)
    if self.closed or not time or type(deadline) ~= "number" or deadline ~= deadline
        or deadline <= time or deadline > time + 45 or not matches(self, proposal) then
        return false, "Native Heist lease scope or deadline changed"
    end
    local state, reason = read(self, true)
    local sequence = proposal.intent.sequence
    if not state then return false, reason end
    if self.lease or self.epoch.live or state.pending ~= nil or state.running or state.inflight ~= nil
        or state.counter ~= sequence - 1 then return false, "Native Heist controller contention" end
    local intent = proposal.intent
    local token = {sequence = sequence, actionName = actions[intent.kind],
        arg1 = intent.kind == "heistStart" and intent.heistId
            or intent.kind ~= "heistCollect" and intent.rowId or nil, startedAt = time}
    local lease = {proposal = proposal, token = token, sequence = sequence, deadline = deadline}
    self.lease, self.epoch.live = lease, lease
    lease.release = function() return self:Release(proposal) end
    -- The bound port proves these primitives are non-yielding. No native worker
    -- can run between this compare and the three writes.
    local ok = pcall(function()
        self.port:Write("pending", token)
        self.port:Write("counter", sequence)
        self.epoch.counterSeen = sequence
        self.port:Write("running", true)
    end)
    if not ok then self:Release(proposal); return false, "Native Heist lease write failed" end
    repaint(self)
    return true, nil
end

function Methods:Owns(proposal)
    local lease, time = self.lease, now(self)
    if self.closed or not lease or lease.proposal ~= proposal or not time or time >= lease.deadline
        or not matches(self, proposal) or self.epoch.live ~= lease then return false end
    local state = read(self, true)
    return state ~= nil and state.pending == lease.token and state.counter == lease.sequence
        and state.running == true and state.inflight == nil
end

function Methods:Release(proposal)
    local lease = self.lease
    if not lease or lease.proposal ~= proposal then return false, "No owned native Heist lease", "absent" end
    -- Use the captured port even after the broader controller/build guard fails.
    -- Exact token identity is the only cleanup authority; never refund sequence.
    local state = read(self, false)
    if not state then return false, "Owned native Heist cleanup read unavailable" end
    local ok = true
    if state.pending == lease.token then
        ok = pcall(function()
            self.port:Write("pending", nil)
            lease.clearedPending = true
            if state.running then self.port:Write("running", false) end
        end)
    elseif state.pending == nil and lease.clearedPending == true
        and state.counter == lease.sequence and state.running then
        -- The prior non-yielding cleanup cleared this exact token before its
        -- second primitive failed. A new native act increments the counter.
        ok = pcall(self.port.Write, self.port, "running", false)
    end
    if not ok then return false, "Native Heist lease cleanup failed" end
    self.lease = nil
    if self.epoch.live == lease then self.epoch.live = nil end
    repaint(self)
    return true, nil
end

function Methods:Close()
    if self.lease then self:Release(self.lease.proposal) end
    self.closed = true
end

-- Deliberately narrow reflection: one reviewed module, one actor and one helper.
-- No captured native worker is invoked; only its three scheduling fields change.
local SOURCE = "11e1d4138dcf5db66aa9b1f4f69d0298bd3b66f8173e13ee4b81dba8f104ec8a"
local REGISTRY = "__IDLE_MAFIA_EMBER_HEIST_EPOCH_V1"
local function child(parent, name, class)
    local value = parent and parent:FindFirstChild(name)
    return value and value.Parent == parent and value:IsA(class) and value or nil
end
local function primitives(readValues, writeValue, isC)
    if type(readValues) ~= "function" or type(writeValue) ~= "function" or type(isC) ~= "function"
        or not isC(readValues) or not isC(writeValue) then return false end
    local cell = nil
    local function dummy(value, write) if write then cell = value end; return cell end
    local marker = {}
    local thread = coroutine.create(function()
        if type(readValues(dummy)) ~= "table" then return false end
        for _, value in ipairs({17, true, marker}) do
            writeValue(dummy, 1, value)
            if dummy() ~= value or readValues(dummy)[1] ~= value then return false end
        end
        writeValue(dummy, 1, nil)
        return dummy() == nil and readValues(dummy)[1] == nil
    end)
    local ok, valid = coroutine.resume(thread)
    return ok and valid == true and coroutine.status(thread) == "dead"
end
function NativeHeistLease.bind(deps)
    if type(deps) ~= "table" or type(deps.env) ~= "table" or type(deps.registry) ~= "table"
        or type(deps.requireModule) ~= "function" or type(deps.clock) ~= "table" then
        return nil, "Native Heist binding capabilities unavailable"
    end
    local env, game = deps.env, deps.game
    local readValues, writeValue = env.getupvalues, env.setupvalue
    if type(env.filtergc) ~= "function" or type(env.getfenv) ~= "function"
        or type(env.decompile) ~= "function" or type(env.crypt) ~= "table"
        or type(env.crypt.hash) ~= "function" or not primitives(readValues, writeValue, env.iscclosure) then
        return nil, "Non-yielding native Heist primitives unavailable"
    end
    local ok, result, reason = pcall(function()
        local build, jobId = game.PlaceVersion, game.JobId
        if game.PlaceId ~= 73897506680154 or (build ~= 648 and build ~= 653) then return nil, "Unreviewed Heist build" end
        local players, replicated = game:GetService("Players"), game:GetService("ReplicatedStorage")
        local player = players.LocalPlayer
        local scripts = child(player, "PlayerScripts", "PlayerScripts")
        local client = child(scripts, "MWClient", "LocalScript")
        local module = child(client, "HeistsTab", "ModuleScript")
        local stateModule = child(client, "State", "ModuleScript")
        local mw = child(replicated, "MW", "Folder")
        local remotes = child(mw, "Remotes", "Folder")
        local remote = child(remotes, "HeistAction", "RemoteFunction")
        if not module or not stateModule or not remote or not player or not text(jobId) then
            return nil, "Native Heist instances unavailable"
        end
        local source = env.decompile(module)
        if type(source) ~= "string" or #source ~= 69223 or env.crypt.hash(source, "sha256"):lower() ~= SOURCE then
            return nil, "Native Heist source changed"
        end
        local state = deps.requireModule(stateModule)
        local candidates = env.filtergc("function", {Name = "act", Constants = {"sequence", "actionName", "startedAt"}}, false)
        local actor, count = nil, 0
        if type(candidates) ~= "table" then return nil, "Native Heist actor unavailable" end
        for _, fn in pairs(candidates) do
            if type(fn) == "function" and env.getfenv(fn).script == module then actor, count = fn, count + 1 end
        end
        if count ~= 1 then return nil, "Native Heist actor ambiguous" end
        local values = readValues(actor)
        local helper, context, refresh = values[5], values[6], values[4]
        if not integer(values[2], 0) or type(values[3]) ~= "boolean" or type(helper) ~= "function"
            or type(context) ~= "table" or type(refresh) ~= "function" or type(values[7]) ~= "function"
            or context.player ~= player or context.State ~= state or type(context.Remotes) ~= "table"
            or type(context.Remotes.HeistAction) ~= "table" or context.Remotes.HeistAction.Instance ~= remote then
            return nil, "Native Heist actor layout changed"
        end
        local helperValues = readValues(helper)
        if helperValues[2] ~= context then return nil, "Native Heist helper changed" end
        local wrapper = context.Remotes.HeistAction
        local retired = false
        local port = {}
        function port:Current()
            if game.PlaceVersion ~= build or game.JobId ~= jobId then retired = true end
            if retired or players.LocalPlayer ~= player or player.Name ~= deps.account
                or child(player, "PlayerScripts", "PlayerScripts") ~= scripts
                or child(scripts, "MWClient", "LocalScript") ~= client
                or child(client, "HeistsTab", "ModuleScript") ~= module
                or child(client, "State", "ModuleScript") ~= stateModule
                or child(replicated, "MW", "Folder") ~= mw or child(mw, "Remotes", "Folder") ~= remotes
                or child(remotes, "HeistAction", "RemoteFunction") ~= remote
                or context.player ~= player or context.State ~= state or context.Remotes.HeistAction ~= wrapper
                or wrapper.Instance ~= remote then return false end
            local current = readValues(actor)
            return current[5] == helper and current[6] == context and current[4] == refresh
                and current[7] == values[7] and readValues(helper)[2] == context
        end
        function port:Read()
            local current = readValues(actor)
            return {pending = current[1], counter = current[2], running = current[3], inflight = readValues(helper)[1]}
        end
        function port:Write(key, value)
            local indexes = {pending = 1, counter = 2, running = 3}
            assert(indexes[key], "Unsupported native Heist field")
            writeValue(actor, indexes[key], value)
        end
        function port:Refresh()
            -- Repaint after the non-yielding transaction; no native RPC/worker.
            if type(deps.defer) == "function" then deps.defer(function() if port:Current() then pcall(refresh) end end) end
        end
        local previous = rawget(deps.registry, REGISTRY)
        local epoch
        if type(previous) == "table" and previous.actor == actor and previous.context == context
            and previous.module == module and previous.jobId == jobId and previous.account == player.Name
            and not previous.retired then epoch = previous end
        if not epoch then
            epoch = {id = game:GetService("HttpService"):GenerateGUID(false), counterSeen = values[2],
                actor = actor, context = context, module = module, jobId = jobId, account = player.Name}
            rawset(deps.registry, REGISTRY, epoch)
        end
        return NativeHeistLease.new(port, deps.clock, {account = player.Name,
            place = tostring(game.PlaceId), jobId = jobId, sourceKey = SOURCE}, epoch)
    end)
    if not ok then return nil, "Native Heist binding inspection failed" end
    return result, reason
end

return NativeHeistLease
