-- Source-bound arbitration around the game's shared act queue. Never writes its counter or flags.
local Controller = {}
local MAX = 9007199254740991
local initActIndex = {[654] = 37, [655] = 38}
local actions = {start = true, collect = true, help = true, sabotage = true}
local function integer(value, low)
    return type(value) == "number" and value == value and value % 1 == 0 and value >= low and value <= MAX
end
local function text(value)
    return type(value) == "string" and #value > 0 and #value <= 120 and not value:find("[%c]")
end
local function child(parent, name, class)
    local value = parent and parent:FindFirstChild(name)
    return value and value.Parent == parent and value:IsA(class) and value or nil
end
local function ancestor(value, root)
    for _ = 1, 16 do
        if value == root then return true end
        if value == nil then return false end
        value = value.Parent
    end
    return false
end
local function copied(value)
    local count, seen = 0, {}
    local function clone(item, depth)
        count = count + 1
        if count > 4096 or depth > 8 then error("Heist reply too large") end
        local kind = type(item)
        if kind == "nil" or kind == "boolean" then return item end
        if kind == "string" and #item <= 4096 then return item end
        if kind == "number" and item == item and item > -math.huge and item < math.huge then return item end
        if kind ~= "table" or seen[item] then error("Invalid Heist reply") end
        seen[item] = true
        local out = {}
        for key, part in pairs(item) do
            if not (text(key) or integer(key, 1)) then error("Invalid Heist reply key") end
            out[key] = clone(part, depth + 1)
        end
        return out
    end
    return clone(value, 1)
end

function Controller.bind(game, requireModule, readUpvalues)
    if game == nil or type(requireModule) ~= "function" or type(readUpvalues) ~= "function" then return nil end
    local ok, result = pcall(function()
        local version, place = game.PlaceVersion, 73897506680154
        local actIndex = initActIndex[version]
        if game.PlaceId ~= place or not actIndex then return nil end
        local players = game:GetService("Players")
        local player = players.LocalPlayer
        local scripts = child(player, "PlayerScripts", "PlayerScripts")
        local client = child(scripts, "MWClient", "LocalScript")
        local replicated = game:GetService("ReplicatedStorage")
        local mw = child(replicated, "MW", "Folder")
        local remotes = child(mw, "Remotes", "Folder")
        local stateModule, configModule = child(client, "State", "ModuleScript"), child(mw, "Config", "ModuleScript")
        local module, linkModule = child(client, "HeistsTab", "ModuleScript"), child(client, "RemoteLink", "ModuleScript")
        local remote, rulesModule = child(remotes, "HeistAction", "RemoteFunction"), child(mw, "ClientRules", "ModuleScript")
        if not stateModule or not configModule or not module or not linkModule or not remote then return nil end
        local state, config, api, link = requireModule(stateModule), requireModule(configModule), requireModule(module), requireModule(linkModule)
        if type(state) ~= "table" or type(state.latest) ~= "function" or type(config) ~= "table"
            or type(api) ~= "table" or type(api.init) ~= "function" or type(link) ~= "table"
            or type(link.wrap) ~= "function" then return nil end
        local init, wrap, latest = api.init, link.wrap, state.latest
        local first = readUpvalues(init)
        if type(first) ~= "table" or type(first[1]) ~= "table" or not first[2]
            or not first[2]:IsA("Frame") or type(first[actIndex]) ~= "function" then return nil end
        local ctx, frame, act = first[1], first[2], first[actIndex]
        local a = readUpvalues(act)
        if type(a) ~= "table" or type(a[4]) ~= "function" or type(a[5]) ~= "function"
            or type(a[7]) ~= "function" then return nil end
        local paint, invokeMutation, refresh, gui = a[4], a[5], a[7], ctx.gui
        local wrapped = wrap(remotes)
        local lookup = wrapped.FindFirstChild
        local linked = wrapped:FindFirstChild("HeistAction")
        if type(linked) ~= "table" or linked.Instance ~= remote or linked.Name ~= "HeistAction"
            or type(linked.InvokeServer) ~= "function" then return nil end
        local invoke, closed, retired, active, lastSequence = linked.InvokeServer, false, false, nil, 0
        local function observe()
            if closed or retired or game.PlaceId ~= place or game.PlaceVersion ~= version or players.LocalPlayer ~= player
                or child(scripts, "MWClient", "LocalScript") ~= client or child(replicated, "MW", "Folder") ~= mw
                or child(mw, "Remotes", "Folder") ~= remotes or child(client, "State", "ModuleScript") ~= stateModule
                or child(mw, "Config", "ModuleScript") ~= configModule or state.latest ~= latest
                or child(client, "HeistsTab", "ModuleScript") ~= module or api.init ~= init
                or child(client, "RemoteLink", "ModuleScript") ~= linkModule or link.wrap ~= wrap
                or child(mw, "ClientRules", "ModuleScript") ~= rulesModule
                or child(remotes, "HeistAction", "RemoteFunction") ~= remote or linked.InvokeServer ~= invoke
                or ctx.State ~= state or ctx.Config ~= config or ctx.player ~= player or ctx.gui ~= gui
                or child(player, "PlayerGui", "PlayerGui") ~= gui.Parent
                or child(gui.Parent, gui.Name, "ScreenGui") ~= gui or not ancestor(frame, gui)
                or type(ctx.Remotes) ~= "table" or ctx.Remotes.HeistAction ~= linked
                or wrapped.FindFirstChild ~= lookup or wrapped:FindFirstChild("HeistAction") ~= linked then return nil end
            local i, current, invocation = readUpvalues(init), readUpvalues(act), readUpvalues(invokeMutation)
            if type(i) ~= "table" or i[1] ~= ctx or i[2] ~= frame or i[actIndex] ~= act
                or type(current) ~= "table" or not integer(current[2], lastSequence) or current[2] >= MAX
                or type(current[3]) ~= "boolean" or current[4] ~= paint or current[5] ~= invokeMutation
                or current[6] ~= ctx or current[7] ~= refresh or type(invocation) ~= "table" or invocation[2] ~= ctx
                or invocation[1] ~= nil and type(invocation[1]) ~= "table" then return nil end
            local pending = current[1]
            if pending ~= nil and (type(pending) ~= "table" or not integer(pending.sequence, 1)
                or pending.sequence > current[2] or not text(pending.actionName)
                or pending.sent ~= nil and type(pending.sent) ~= "boolean") then return nil end
            lastSequence = current[2]
            local busy = current[3] or pending ~= nil or invocation[1] ~= nil
            local physical = invocation[1] ~= nil and invocation[1].done ~= true
            local data = latest()
            if type(data) ~= "table" or data.userId ~= nil and data.userId ~= player.UserId then return nil end
            local serverNow = data.serverNow
            if serverNow ~= nil and (type(serverNow) ~= "number" or serverNow ~= serverNow or serverNow < 0 or serverNow > MAX) then return nil end
            return {sequence = current[2], working = current[3], invocationPending = physical, serverNow = serverNow,
                nativeBusy = busy, controllersClear = not busy and active == nil,
                pending = pending and {sequence = pending.sequence, actionName = pending.actionName,
                    arg1 = pending.arg1, sent = pending.sent} or nil}
        end
        local function read()
            local success, value = pcall(observe)
            if not success or not value then retired = true; return nil end
            return value
        end
        if not read() then return nil end
        return {Current = function() return read() ~= nil end, Read = read,
            Busy = function()
                local value = read()
                return value == nil or value.working or value.invocationPending
            end,
            Start = function(sequence, action, arg1, onSuccess)
                local value = read()
                local argValid = action == "collect" and arg1 == nil
                    or action ~= "collect" and (text(arg1) or integer(arg1, 1))
                if not value or not value.controllersClear or not integer(sequence, 1)
                    or sequence ~= value.sequence + 1 or not actions[action] or not argValid
                    or type(onSuccess) ~= "function" then return false end
                local owned = {sequence = sequence, action = action, arg1 = arg1}
                active = owned
                -- act increments its own counter before any native worker yields.
                -- Once entered, even an exception is ambiguous and must retain custody.
                pcall(act, action, arg1, function(reply)
                    local current = read()
                    if active ~= owned or not current or current.sequence ~= sequence
                        or type(reply) ~= "table" or reply.ok ~= true or owned.delivered then return end
                    local success, copy = pcall(copied, reply)
                    if not success then return end
                    owned.delivered = true
                    pcall(onSuccess, copy)
                end)
                return true
            end,
            Release = function(sequence)
                local value = read()
                if not value or value.nativeBusy or not active or active.sequence ~= sequence then return false end
                active = nil
                return true
            end,
            Close = function() closed = true end}
    end)
    return ok and result or nil
end

return Controller
