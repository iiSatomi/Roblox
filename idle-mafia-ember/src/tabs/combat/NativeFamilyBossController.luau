-- Read-only 654 FamilyBossView preflight. No attack call or estimated damage.
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
    if not game or type(requireModule) ~= "function" or type(readUpvalues) ~= "function" then return nil end
    local ok, result = pcall(function()
        if game.PlaceId ~= 73897506680154 or game.PlaceVersion ~= 654 then return nil end
        local players, replicated = game:GetService("Players"), game:GetService("ReplicatedStorage")
        local player = players.LocalPlayer
        local scripts = child(player, "PlayerScripts", "PlayerScripts")
        local client, mw = child(scripts, "MWClient", "LocalScript"), child(replicated, "MW", "Folder")
        local family = child(client, "FamilyTab", "ModuleScript")
        local module = child(family, "FamilyBossView", "ModuleScript")
        local stateModule, configModule = child(client, "State", "ModuleScript"), child(mw, "Config", "ModuleScript")
        local linkModule, remotes = child(client, "RemoteLink", "ModuleScript"), child(mw, "Remotes", "Folder")
        local remote = child(remotes, "FamilyBossAction", "RemoteFunction")
        if not module or not stateModule or not configModule or not linkModule or not remote then return nil end
        local api, state, config, link = requireModule(module), requireModule(stateModule), requireModule(configModule), requireModule(linkModule)
        if type(api) ~= "table" or type(api.init) ~= "function" or type(api.show) ~= "function"
            or type(api.hide) ~= "function" or type(api.refresh) ~= "function" or type(state) ~= "table"
            or type(state.latest) ~= "function" or type(link) ~= "table" or type(link.wrap) ~= "function"
            or type(config) ~= "table" or type(config.FAMILY_BOSS) ~= "table" or type(config.COMBAT) ~= "table"
            or not integer(player.UserId, 1) then return nil end
        local init, show, hide, refresh, latest, wrap = api.init, api.show, api.hide, api.refresh, state.latest, link.wrap
        local first = readUpvalues(init)
        if type(first) ~= "table" or type(first[1]) ~= "table" or type(first[6]) ~= "function" then return nil end
        local ctx, attack = first[1], first[6]
        local values = readUpvalues(attack)
        if type(values) ~= "table" or type(values[5]) ~= "function" or type(values[18]) ~= "function" then return nil end
        local freeNow, invoke = values[5], values[18]
        local linked = type(ctx.Remotes) == "table" and ctx.Remotes.FamilyBossAction
        if type(linked) ~= "table" or linked.Instance ~= remote or linked.Name ~= "FamilyBossAction"
            or type(linked.InvokeServer) ~= "function" then return nil end
        local remoteInvoke, userId = linked.InvokeServer, player.UserId
        local rules, combat = config.FAMILY_BOSS, config.COMBAT
        local cost, hospital, stages = rules.staminaCost, combat.hospitalHealth, rules.stages
        if not integer(cost, 1) or cost > 10000 or not integer(hospital, 1) or type(stages) ~= "table" or #stages ~= 5 then return nil end
        local stageRows = {}
        for index = 1, 5 do
            if type(stages[index]) ~= "table" then return nil end
            stageRows[index] = stages[index]
        end
        local closed, retired = false, false
        local function observe()
            if closed or retired or game.PlaceId ~= 73897506680154 or game.PlaceVersion ~= 654
                or players.LocalPlayer ~= player or player.UserId ~= userId
                or child(scripts, "MWClient", "LocalScript") ~= client or child(replicated, "MW", "Folder") ~= mw
                or child(client, "FamilyTab", "ModuleScript") ~= family or child(family, "FamilyBossView", "ModuleScript") ~= module
                or child(client, "State", "ModuleScript") ~= stateModule or child(mw, "Config", "ModuleScript") ~= configModule
                or child(client, "RemoteLink", "ModuleScript") ~= linkModule or child(mw, "Remotes", "Folder") ~= remotes
                or child(remotes, "FamilyBossAction", "RemoteFunction") ~= remote or link.wrap ~= wrap or state.latest ~= latest
                or api.init ~= init or api.show ~= show or api.hide ~= hide or api.refresh ~= refresh
                or ctx.State ~= state or ctx.Config ~= config or ctx.player ~= player
                or type(ctx.Remotes) ~= "table" or ctx.Remotes.FamilyBossAction ~= linked or linked.InvokeServer ~= remoteInvoke
                or config.FAMILY_BOSS ~= rules or config.COMBAT ~= combat or rules.stages ~= stages
                or rules.staminaCost ~= cost or combat.hospitalHealth ~= hospital then return nil end
            for index = 1, 5 do if stages[index] ~= stageRows[index] then return nil end end
            local i, a, invoked = readUpvalues(init), readUpvalues(attack), readUpvalues(invoke)
            if type(i) ~= "table" or type(a) ~= "table" or type(invoked) ~= "table"
                or i[1] ~= ctx or i[6] ~= attack or i[16] ~= a[1]
                or a[1] ~= nil and type(a[1]) ~= "table" or type(a[2]) ~= "boolean" or not number(a[3], 0)
                or a[4] ~= ctx or a[5] ~= freeNow or a[18] ~= invoke or invoked[1] ~= ctx then return nil end
            local cooldown = math.max(0, a[3] - os.clock())
            return {staminaCost = cost, hospitalHealth = hospital, hitBackKnown = false,
                busy = a[2], cooldown = cooldown, controllersClear = not a[2] and cooldown == 0}
        end
        local function current()
            local checked, frame = pcall(observe)
            if not checked or not frame then retired = true; return nil end
            return frame
        end
        if not current() then return nil end
        return {Current = function() return current() ~= nil end,
            Busy = function() local frame = current(); return not frame or frame.busy end,
            Close = function() closed = true end,
            Read = function(native)
                local frame = current()
                if not frame or type(native) ~= "table" or native.fullSync ~= true or native.userId ~= userId
                    or type(native.stats) ~= "table" or not integer(native.stats.maxHealth, 1)
                    or type(native.pools) ~= "table" or not number(native.pools.health, 0)
                    or native.pools.health > native.stats.maxHealth or not number(native.pools.stamina, 0) then return nil end
                local data = latest()
                if type(data) ~= "table" or type(data.stats) ~= "table" or type(data.pools) ~= "table"
                    or data.stats.maxHealth ~= native.stats.maxHealth or data.pools.health ~= native.pools.health
                    or data.pools.stamina ~= native.pools.stamina or type(data.family) ~= "table"
                    or type(native.family) ~= "table" or data.family.id ~= native.family.id then return nil end
                frame.health, frame.maxHealth, frame.stamina = native.pools.health, native.stats.maxHealth, native.pools.stamina
                return current() and frame or nil
            end}
    end)
    return ok and result or nil
end
return Controller
