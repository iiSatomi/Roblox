-- Own only PrestigeModal's reviewed busy cell; native confirmations remain manual.
local NativePrestigeLease, Methods = {}, {}
Methods.__index = Methods
local MAX = 9007199254740991
local scopes = {"session", "account", "place", "release"}
local REGISTRY = "__IDLE_MAFIA_EMBER_PRESTIGE_OWNER_V1"
local SOURCE = "e08a7b50420068cea8889de24070d5b6a104cc41e1401eb25c80ac871c92ad82"
local function finite(v) return type(v) == "number" and v == v and v >= 0 and v <= MAX end
local function integer(v, low, high) return finite(v) and v % 1 == 0 and v >= low and v <= high end
local function text(v) return type(v) == "string" and #v > 0 and #v <= 200 and not v:find("[%c]") end
local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for k, v in pairs(a) do if b[k] ~= v then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end
local function at(self)
    local ok, value = pcall(self.clock.Now, self.clock)
    return ok and finite(value) and value or nil
end
local function state(self)
    local ok, value = pcall(self.port.Read, self.port)
    if not ok or type(value) ~= "table" or (type(value.busy) ~= "boolean" and type(value.busy) ~= "table")
        or type(value.confirmationPending) ~= "boolean" or type(value.modalOpen) ~= "boolean" then return nil end
    return value
end
local intentFields = {kind=true,rankBefore=true,nextRank=true,levelBefore=true,xpBefore=true,requiredLevel=true,
    catalogKey=true,allowReset=true,targetRank=true,maxResets=true,attemptedBefore=true}
local function matches(self, p)
    local i = type(p) == "table" and p.intent
    if type(i) ~= "table" or p.feature ~= "prestige" or i.kind ~= "prestigeReset"
        or not integer(i.rankBefore, 0, 5) or i.nextRank ~= i.rankBefore + 1
        or p.actionKey ~= "prestige:" .. i.rankBefore .. ":" .. i.nextRank
        or not integer(p.revision, 0, MAX) or not integer(i.levelBefore, 1, MAX) or not finite(i.xpBefore)
        or i.allowReset ~= true or not integer(i.targetRank, i.nextRank, 6)
        or not integer(i.maxResets, 1, 6) or not integer(i.attemptedBefore, 0, i.maxResets - 1)
        or not integer(i.requiredLevel, 1, i.levelBefore) or type(i.catalogKey) ~= "string" or #i.catalogKey ~= 64
        or not i.catalogKey:match("^[%x]+$")
        or type(p.resources) ~= "table" or next(p.resources) ~= nil then return false end
    for _, key in ipairs(scopes) do if p[key] ~= self.identity[key] then return false end end
    for k in pairs(i) do if not intentFields[k] then return false end end
    return true
end
local function expire(self)
    local time = at(self)
    if self.active and (not time or time >= self.active.deadline) then self:Release(self.active.proposal) end
    return time
end
local function current(self)
    if self.closed or self.epoch.retired then return false end
    local ok, valid = pcall(self.port.Current, self.port)
    if not ok or valid ~= true then
        self.epoch.retired = true
        self.reason = "Native Prestige source changed; owner retired"
        self:Close()
        return false
    end
    return true
end
local function ownedState(self)
    local value = state(self)
    if not value then return nil end
    local active = self.active
    if active and value.busy ~= active.token then
        self.epoch.retired = true
        self.reason = "Native Prestige busy identity changed"
        self:Close()
        return nil
    end
    -- Native true is authoritative ongoing native work. A table is valid only
    -- when its identity is this owner's exact opaque token.
    if type(value.busy) == "table" and (not active or value.busy ~= active.token) then return nil end
    return value
end

function NativePrestigeLease.new(port, clock, identity, epoch)
    if type(port) ~= "table" or port.nonYielding ~= true or type(port.Current) ~= "function"
        or type(port.Read) ~= "function" or type(port.Facts) ~= "function" or type(port.CompareBusy) ~= "function"
        or type(clock) ~= "table" or type(clock.Now) ~= "function" or type(identity) ~= "table" or type(epoch) ~= "table" then
        return nil, "Non-yielding native Prestige capabilities required"
    end
    local own = {}
    for _, key in ipairs(scopes) do if not text(identity[key]) then return nil, "Native Prestige scope unavailable" end; own[key] = identity[key] end
    if epoch.binding or epoch.physical or epoch.retired then return nil, "Previous native Prestige ownership remains unresolved" end
    local self = setmetatable({port = port, clock = clock, identity = own, epoch = epoch, closed = false}, Methods)
    if not current(self) then return nil, self.reason end
    local value = state(self)
    if not value or type(value.busy) ~= "boolean" then return nil, "Native Prestige busy provenance unavailable" end
    -- Visible/pending manual dialogs and native true may be observed while the
    -- human finishes them. Only a later exact false permits an atomic claim.
    epoch.binding = self
    return self, nil
end

function Methods:Current() return current(self) end
function Methods:Read()
    expire(self)
    if not current(self) then return nil end
    local before = ownedState(self)
    if not before then return nil end
    local ok, facts = pcall(self.port.Facts, self.port)
    local after = ownedState(self)
    if not ok or type(facts) ~= "table" or not integer(facts.rank, 0, 6) or not integer(facts.level, 1, MAX)
        or not finite(facts.xp) or type(facts.ready) ~= "boolean" or not current(self) or not after
        or after.busy ~= before.busy or after.confirmationPending ~= before.confirmationPending or after.modalOpen ~= before.modalOpen then return nil end
    return {rank = facts.rank, level = facts.level, xp = facts.xp, ready = facts.ready,
        busy = before.busy ~= false, confirmationPending = before.confirmationPending, modalOpen = before.modalOpen,
        controllersClear = before.busy == false and self.active == nil and self.epoch.physical == nil
            and not before.confirmationPending and not before.modalOpen}
end
function Methods:Acquire(p, deadline)
    local time = expire(self)
    if not current(self) or not time or not finite(deadline) or deadline <= time or deadline > time + 45 or not matches(self, p) then
        return false, "Native Prestige scope or deadline changed"
    end
    local value = ownedState(self)
    if self.active or self.epoch.physical or self.epoch.binding ~= self or not value or value.busy ~= false
        or value.confirmationPending or value.modalOpen then return false, "Native Prestige or a manual confirmation owns the controller" end
    local intent = {}
    for k, v in pairs(p.intent) do intent[k] = v end
    local active = {proposal = p, token = {}, deadline = deadline, intent = intent, actionKey = p.actionKey, revision = p.revision}
    self.active = active -- Retain cleanup authority even if a primitive throws after writing.
    local ok, claimed = pcall(self.port.CompareBusy, self.port, false, active.token)
    local after = state(self)
    if not ok or claimed ~= true or not after or after.busy ~= active.token then
        self:Release(p)
        return false, "Native Prestige guard claim unconfirmed"
    end
    return true, nil
end
function Methods:Owns(p)
    local time = expire(self)
    if not current(self) or not time then return false end
    local active, value = self.active, ownedState(self)
    return active ~= nil and not active.released and active.proposal == p and self.epoch.binding == self
        and matches(self, p) and active.actionKey == p.actionKey and active.revision == p.revision and same(active.intent, p.intent)
        and value ~= nil and value.busy == active.token
end
function Methods:Invoke(p, invoke, ...)
    if type(invoke) ~= "function" or not self:Owns(p) or self.epoch.physical or self.active.invoked then return false, "Exact native Prestige invocation ownership required" end
    local value = ownedState(self)
    if not value or value.confirmationPending or value.modalOpen then return false, "Complete the native manual dialog before Prestige can run" end
    local active = self.active
    active.invoked = true -- This proposal owns exactly one entry into the executor.
    local physical = {owner = self, active = active}
    self.epoch.physical = physical
    local result = table.pack(pcall(invoke, ...))
    if self.epoch.physical == physical then self.epoch.physical = nil else self.epoch.retired = true end
    local time = at(self)
    if self.closed or active.released or not time or time >= active.deadline then self:Release(p) end
    if not result[1] then error(result[2], 0) end
    if not self:Owns(p) then return false, "Native Prestige invocation owner changed before return" end
    return table.unpack(result, 2, result.n)
end
function Methods:Release(p)
    local active = self.active
    if not active or active.proposal ~= p then return false, "No owned native Prestige guard" end
    active.released = true
    if self.epoch.physical then
        self.reason = "Native Prestige physical return unresolved; exact busy custody retained"
        return true, nil, "physical"
    end
    local before = state(self)
    if not before then self.reason = "Native Prestige cleanup read unavailable; exact custody retained"; return false, self.reason end
    if before.busy == active.token then
        local ok, cleared = pcall(self.port.CompareBusy, self.port, active.token, false)
        local after = state(self)
        if not ok or cleared ~= true or not after or after.busy ~= false then
            self.reason = "Native Prestige cleanup unconfirmed; exact busy custody retained"
            return false, self.reason
        end
    end
    -- A foreign value is never overwritten. Its observed absence of our exact
    -- token ends only our custody; source retirement prevents further use.
    self.active = nil
    if not self.closed then self.reason = nil end
    if self.closed and self.epoch.binding == self then self.epoch.binding = nil end
    return true, nil
end
function Methods:Status()
    expire(self)
    current(self)
    return {closed = self.closed, active = self.active ~= nil and not self.active.released,
        physical = self.epoch.physical ~= nil, custody = self.active ~= nil, reason = self.reason}
end
function Methods:Close()
    self.closed = true
    if self.active then self:Release(self.active.proposal) end
    local complete = self.active == nil and self.epoch.physical == nil
    if complete and self.epoch.binding == self then self.epoch.binding = nil end
    return complete
end
function NativePrestigeLease.cleanup(registry)
    if type(registry) ~= "table" then return false, "Native Prestige registry unavailable" end
    local epoch = rawget(registry, REGISTRY)
    if epoch == nil then return true, nil end
    if type(epoch) ~= "table" or epoch.sourceKey ~= SOURCE or type(epoch.context) ~= "table" or type(epoch.init) ~= "function"
        or not text(epoch.job) or (epoch.build ~= 648 and epoch.build ~= 653 and epoch.build ~= 654) then return false, "Native Prestige ownership record is ambiguous" end
    if epoch.physical then return false, "Native Prestige physical custody remains unresolved" end
    local owner = epoch.binding
    if owner == nil then return true, nil end
    if type(owner) ~= "table" or owner.closed ~= true or type(owner.Close) ~= "function" then return false, "Previous native Prestige owner remains active or ambiguous" end
    local ok, complete = pcall(owner.Close, owner)
    if rawget(registry, REGISTRY) ~= epoch or not ok or complete ~= true or epoch.binding ~= nil or epoch.physical then
        return false, "Native Prestige exact cleanup remains unconfirmed"
    end
    return true, nil
end

local function child(parent, name, class)
    local value = parent and parent:FindFirstChild(name)
    return value and value.Parent == parent and value:IsA(class) and value or nil
end
local function primitives(get, set, isC)
    if type(get) ~= "function" or type(set) ~= "function" or type(isC) ~= "function" or not isC(get) or not isC(set) then return false end
    local cell = false
    local function dummy(value, write) if write then cell = value end; return cell end
    local marker = {}
    local thread = coroutine.create(function()
        if type(get(dummy)) ~= "table" then return false end
        set(dummy, 1, marker)
        if dummy() ~= marker or get(dummy)[1] ~= marker then return false end
        set(dummy, 1, false)
        return dummy() == false and get(dummy)[1] == false
    end)
    local ok, valid = coroutine.resume(thread)
    return ok and valid == true and coroutine.status(thread) == "dead"
end
function NativePrestigeLease.bind(deps)
    if type(deps) ~= "table" or type(deps.env) ~= "table" or type(deps.registry) ~= "table" or type(deps.requireModule) ~= "function"
        or type(deps.clock) ~= "table" or type(deps.identity) ~= "table" then return nil, "Native Prestige binding capabilities unavailable" end
    local env, game, registry = deps.env, deps.game, deps.registry
    local get, set = env.getupvalues, env.setupvalue
    if type(env.decompile) ~= "function" or type(env.crypt) ~= "table" or type(env.crypt.hash) ~= "function"
        or not primitives(get, set, env.iscclosure) then return nil, "Non-yielding native Prestige reflection unavailable" end
    local ok, owner, why = pcall(function()
        local cleaned, reason = NativePrestigeLease.cleanup(registry)
        if not cleaned then return nil, reason end
        local build, job = game.PlaceVersion, game.JobId
        if game.PlaceId ~= 73897506680154 or (build ~= 648 and build ~= 653 and build ~= 654) or not text(job) then return nil, "Unreviewed Prestige build" end
        local players, replicated = game:GetService("Players"), game:GetService("ReplicatedStorage")
        local player = players.LocalPlayer
        if not player or player.Name ~= deps.identity.account or not integer(player.UserId, 1, MAX)
            or deps.identity.place ~= tostring(game.PlaceId) then return nil, "Native Prestige player identity unavailable" end
        local userId = player.UserId
        local scripts = child(player, "PlayerScripts", "PlayerScripts")
        local client = child(scripts, "MWClient", "LocalScript")
        local module, stateModule = child(client, "PrestigeModal", "ModuleScript"), child(client, "State", "ModuleScript")
        local fightModule = child(client, "FightTab", "ModuleScript")
        local mw = child(replicated, "MW", "Folder")
        local rulesModule, configModule = child(mw, "Prestige", "ModuleScript"), child(mw, "Config", "ModuleScript")
        local remotes = child(mw, "Remotes", "Folder")
        local remote = child(remotes, "PrestigeAction", "RemoteFunction")
        if not module or not stateModule or not fightModule or not rulesModule or not configModule or not remote then return nil, "Native Prestige instances unavailable" end
        local bytes = env.decompile(module)
        if type(bytes) ~= "string" or #bytes ~= 4497 or env.crypt.hash(bytes, "sha256"):lower() ~= SOURCE then return nil, "Unreviewed native Prestige source" end
        local api, stateApi, fight, rules, config = deps.requireModule(module), deps.requireModule(stateModule), deps.requireModule(fightModule), deps.requireModule(rulesModule), deps.requireModule(configModule)
        if type(api) ~= "table" or type(api.init) ~= "function" or type(api.open) ~= "function" or type(fight) ~= "table"
            or type(fight.confirm) ~= "function" or type(stateApi) ~= "table" or type(stateApi.latest) ~= "function"
            or type(rules) ~= "table" or type(rules.rankOf) ~= "function" or type(rules.canPrestige) ~= "function" or type(config) ~= "table" then return nil, "Native Prestige APIs unavailable" end
        local init, open, confirm, latest, rankOf, canPrestige = api.init, api.open, fight.confirm, stateApi.latest, rules.rankOf, rules.canPrestige
        local first = get(init)
        local ctx, root, modal, close, any, paint = first[1], first[2], first[3], first[4], first[7], first[8]
        if type(ctx) ~= "table" or not root or not modal or type(close) ~= "function" or type(any) ~= "function" or type(paint) ~= "function" then return nil, "Native Prestige context unavailable" end
        local gui = ctx.gui
        local confirmationModal = child(root, "ConfirmModal", "Frame")
        local wrapped = type(ctx.Remotes) == "table" and ctx.Remotes.PrestigeAction
        if not confirmationModal or type(wrapped) ~= "table" or wrapped.Name ~= "PrestigeAction" or wrapped.Instance ~= remote or type(wrapped.InvokeServer) ~= "function" then return nil, "Native Prestige wrapper unavailable" end
        local invoke, retired = wrapped.InvokeServer, false
        local epoch
        local port = {nonYielding = true}
        local function layout()
            local i, o, c = get(init), get(open), get(confirm)
            if type(i) ~= "table" or type(o) ~= "table" or type(c) ~= "table" or i[1] ~= ctx or i[2] ~= root or i[3] ~= modal
                or i[4] ~= close or (type(i[5]) ~= "boolean" and type(i[5]) ~= "table") or i[6] ~= rules or i[7] ~= any or i[8] ~= paint
                or o[1] ~= ctx or o[2] ~= rules or o[3] ~= paint or o[4] ~= root or o[5] ~= modal
                or c[1] ~= root or c[4] ~= ctx or c[3] ~= nil and type(c[3]) ~= "function" then error("Native Prestige shared layout changed") end
            return i[5], c[3] ~= nil
        end
        function port:Current()
            if retired or epoch ~= nil and rawget(registry, REGISTRY) ~= epoch or game.PlaceId ~= 73897506680154 or game.PlaceVersion ~= build or game.JobId ~= job or players.LocalPlayer ~= player
                or player.Name ~= deps.identity.account or player.UserId ~= userId or child(player, "PlayerScripts", "PlayerScripts") ~= scripts
                or child(scripts, "MWClient", "LocalScript") ~= client or child(client, "PrestigeModal", "ModuleScript") ~= module
                or child(client, "State", "ModuleScript") ~= stateModule or child(client, "FightTab", "ModuleScript") ~= fightModule
                or child(replicated, "MW", "Folder") ~= mw or child(mw, "Prestige", "ModuleScript") ~= rulesModule
                or child(mw, "Config", "ModuleScript") ~= configModule or child(mw, "Remotes", "Folder") ~= remotes
                or child(remotes, "PrestigeAction", "RemoteFunction") ~= remote or api.init ~= init or api.open ~= open or fight.confirm ~= confirm
                or stateApi.latest ~= latest or rules.rankOf ~= rankOf or rules.canPrestige ~= canPrestige or ctx.State ~= stateApi or ctx.Config ~= config
                or ctx.player ~= player or ctx.gui ~= gui or ctx.confirmDialog ~= confirm or type(ctx.Remotes) ~= "table" or ctx.Remotes.PrestigeAction ~= wrapped
                or wrapped.Name ~= "PrestigeAction" or wrapped.Instance ~= remote or wrapped.InvokeServer ~= invoke
                or env.getupvalues ~= get or env.setupvalue ~= set or child(player, "PlayerGui", "PlayerGui") ~= gui.Parent
                or child(gui.Parent, gui.Name, "ScreenGui") ~= gui or child(child(gui, "Root", "Frame"), "Modals", "Frame") ~= root
                or child(root, "PrestigeModal", "Frame") ~= modal or child(root, "ConfirmModal", "Frame") ~= confirmationModal then retired = true; return false end
            if not pcall(layout) then retired = true; return false end
            return true
        end
        function port:Read()
            local busy, pending = layout()
            local visible, count = root.Visible, 0
            if type(visible) ~= "boolean" then error("Native Prestige modal root unavailable") end
            for _, row in ipairs(root:GetChildren()) do
                count = count + 1
                if count > 128 then error("Native Prestige modal collection unavailable") end
                if row:IsA("GuiObject") and row.Name ~= "Backdrop" then
                    if type(row.Visible) ~= "boolean" then error("Native Prestige modal visibility unavailable") end
                    visible = visible or row.Visible
                end
            end
            return {busy = busy, confirmationPending = pending, modalOpen = visible}
        end
        function port:Facts()
            local data = latest()
            if type(data) ~= "table" or data.userId ~= nil and data.userId ~= userId then return nil end
            local level, xp, rank, ready = data.level, data.xp, rankOf(data), canPrestige(data)
            local after = latest()
            if type(after) ~= "table" or after.userId ~= nil and after.userId ~= userId or after.level ~= level or after.xp ~= xp or rankOf(after) ~= rank then return nil end
            return {rank = rank, level = level, xp = xp, ready = ready}
        end
        function port:CompareBusy(expected, replacement)
            if get(init)[5] ~= expected then return false end
            set(init, 5, replacement)
            return get(init)[5] == replacement
        end
        if not port:Current() then return nil, "Native Prestige source changed during inspection" end
        epoch = rawget(registry, REGISTRY)
        if epoch ~= nil and type(epoch) ~= "table" then return nil, "Native Prestige ownership record is ambiguous" end
        if epoch and epoch.context == ctx and epoch.init == init then
            if epoch.retired or epoch.job ~= job or epoch.build ~= build then return nil, "Native Prestige source epoch retired" end
        else
            epoch = {context = ctx, init = init, job = job, build = build, sourceKey = SOURCE}
            rawset(registry, REGISTRY, epoch)
        end
        return NativePrestigeLease.new(port, deps.clock, deps.identity, epoch)
    end)
    if not ok then return nil, "Native Prestige binding inspection failed" end
    return owner, why
end
return NativePrestigeLease
