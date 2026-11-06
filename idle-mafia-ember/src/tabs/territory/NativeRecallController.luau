-- Read-only arbitration around the reviewed 654 CrewRecall queue/counter.
-- Never starts its autonomous retry loop or writes native state/capabilities.
local Controller = {}
local MAX = 9007199254740991
local function number(value, low)
    return type(value) == "number" and value == value and value >= low and value <= MAX
end
local function integer(value, low) return number(value, low) and value % 1 == 0 end
local function child(parent, name, class)
    local value = parent and parent:FindFirstChild(name)
    return value and value.Parent == parent and value:IsA(class) and value or nil
end
function Controller.bind(game, requireModule, readUpvalues)
    if game == nil or type(requireModule) ~= "function" or type(readUpvalues) ~= "function" then return nil end
    local ok, result = pcall(function()
        if game.PlaceId ~= 73897506680154 or game.PlaceVersion ~= 654 then return nil end
        local players, replicated = game:GetService("Players"), game:GetService("ReplicatedStorage")
        local player = players.LocalPlayer
        local userId = player and player.UserId
        if not integer(userId, 1) then return nil end
        local scripts = child(player, "PlayerScripts", "PlayerScripts")
        local client, mw = child(scripts, "MWClient", "LocalScript"), child(replicated, "MW", "Folder")
        local module, stateModule = child(client, "CrewRecall", "ModuleScript"), child(client, "State", "ModuleScript")
        local clockModule, configModule = child(mw, "ServerClock", "ModuleScript"), child(mw, "Config", "ModuleScript")
        local remotes = child(mw, "Remotes", "Folder")
        local action, status = child(remotes, "TerritoryAction", "RemoteFunction"), child(remotes, "TerritoryStatus", "RemoteFunction")
        if not module or not stateModule or not clockModule or not configModule or not action or not status then return nil end
        local api, state, clock, config = requireModule(module), requireModule(stateModule), requireModule(clockModule), requireModule(configModule)
        if type(api) ~= "table" or type(api.init) ~= "function" or type(api.start) ~= "function"
            or type(api.busy) ~= "function" or type(state) ~= "table" or type(state.latest) ~= "function"
            or type(clock) ~= "table" or type(clock.now) ~= "function" then return nil end
        local init, start, busy, latest, now = api.init, api.start, api.busy, state.latest, clock.now
        local first, initial = readUpvalues(init), readUpvalues(start)
        if type(first) ~= "table" or type(first[1]) ~= "table" or type(first[3]) ~= "function"
            or type(initial) ~= "table" or type(initial[4]) ~= "function" then return nil end
        local ctx, finish, changed = first[1], first[3], initial[4]
        local linkedAction = type(ctx.Remotes) == "table" and ctx.Remotes.TerritoryAction
        local linkedStatus = type(ctx.Remotes) == "table" and ctx.Remotes.TerritoryStatus
        if type(linkedAction) ~= "table" or type(linkedStatus) ~= "table"
            or linkedAction.Instance ~= action or linkedStatus.Instance ~= status
            or type(linkedAction.InvokeServer) ~= "function" or type(linkedStatus.InvokeServer) ~= "function" then return nil end
        local actionInvoke, statusInvoke = linkedAction.InvokeServer, linkedStatus.InvokeServer
        local retired, closed, lastRequestId = false, false, 0
        local function observe()
            if retired or closed or game.PlaceId ~= 73897506680154 or game.PlaceVersion ~= 654
                or players.LocalPlayer ~= player or player.UserId ~= userId or child(scripts, "MWClient", "LocalScript") ~= client
                or child(replicated, "MW", "Folder") ~= mw or child(mw, "Remotes", "Folder") ~= remotes
                or child(client, "CrewRecall", "ModuleScript") ~= module or child(client, "State", "ModuleScript") ~= stateModule
                or child(mw, "Config", "ModuleScript") ~= configModule or child(mw, "ServerClock", "ModuleScript") ~= clockModule
                or child(remotes, "TerritoryAction", "RemoteFunction") ~= action or child(remotes, "TerritoryStatus", "RemoteFunction") ~= status
                or state.latest ~= latest or clock.now ~= now or api.init ~= init or api.start ~= start or api.busy ~= busy
                or ctx.State ~= state or ctx.Config ~= config or ctx.player ~= player or type(ctx.Remotes) ~= "table"
                or ctx.Remotes.TerritoryAction ~= linkedAction or ctx.Remotes.TerritoryStatus ~= linkedStatus
                or linkedAction.InvokeServer ~= actionInvoke or linkedStatus.InvokeServer ~= statusInvoke then return nil end
            local i, s, b = readUpvalues(init), readUpvalues(start), readUpvalues(busy)
            if type(i) ~= "table" or type(s) ~= "table" or type(b) ~= "table"
                or i[1] ~= ctx or i[3] ~= finish or s[1] ~= i[2] or b[1] ~= i[2]
                or not integer(s[2], lastRequestId) or s[2] >= MAX or s[3] ~= clock or s[4] ~= changed
                or s[5] ~= finish or s[6] ~= ctx or i[2] ~= nil and type(i[2]) ~= "table" then return nil end
            local nativeBusy, serverNow = busy(), now()
            if type(nativeBusy) ~= "boolean" or nativeBusy ~= (i[2] ~= nil) or not number(serverNow, 0)
                or serverNow > math.floor(MAX / 1000) then return nil end
            lastRequestId = s[2]
            return {userId = userId, lastRequestId = lastRequestId, epochFloor = math.floor(serverNow * 1000),
                controllersClear = not nativeBusy, busy = nativeBusy}
        end
        local function read()
            local checked, value = pcall(observe)
            if not checked or not value then retired = true; return nil end
            return value
        end
        if not read() then return nil end
        return {Read = read, Current = function() return read() ~= nil end,
            Busy = function() local value = read(); return not value or value.busy end,
            Close = function() closed = true end}
    end)
    return ok and result or nil
end
return Controller
