-- Locate the current public MWClient State and replicated Remotes instances.
local NativeClientBindings = {}

local function reviewedVersion(version)
    return version == 654 or version == 655
end

local function child(parent, name, class)
    if parent == nil then return nil end
    local value = parent:FindFirstChild(name)
    if value == nil or value.Parent ~= parent
        or not value:IsA(class) then return nil end
    return value
end

local function resolve(game, requireModule, readUpvalues, heistControllerModule, recallControllerModule, familyBossControllerModule)
    local players = game:GetService("Players")
    local player = players and players.LocalPlayer
    local scripts = player and child(player, "PlayerScripts", "PlayerScripts")
    local client = child(scripts, "MWClient", "LocalScript")
    local stateModule = child(client, "State", "ModuleScript")
    local replicated = game:GetService("ReplicatedStorage")
    local mw = child(replicated, "MW", "Folder")
    local remotes = child(mw, "Remotes", "Folder")
    local sync = child(remotes, "Sync", "RemoteEvent")
    if stateModule == nil or sync == nil then return nil end
    local state = requireModule(stateModule)
    if type(state) ~= "table" or type(state.data) ~= "table"
        or type(state.latest) ~= "function"
        or type(state.onChanged) ~= "function"
        or type(state.lastSyncClock) ~= "number"
        or state.lastSyncClock ~= state.lastSyncClock then
        return nil
    end
    local latest = state.latest()
    if type(latest) ~= "table" then return nil end
    local dailyBuffRules, config, gameData, gearSets, cityMaps
    local dailyModule = child(mw, "DailyBuffRules", "ModuleScript")
    if dailyModule then
        local ok, value = pcall(requireModule, dailyModule)
        if ok and type(value) == "table"
            and type(value.isWeekend) == "function" then
            dailyBuffRules = value
        end
    end
    local configModule = child(mw, "Config", "ModuleScript")
    if configModule then
        local ok, value = pcall(requireModule, configModule)
        if ok and type(value) == "table" then config = value end
    end
    local gameDataModule = child(mw, "GameData", "ModuleScript")
    if gameDataModule then
        local ok, value = pcall(requireModule, gameDataModule)
        if ok and type(value) == "table" then gameData = value end
    end
    local gearSetsModule = child(mw, "GearSets", "ModuleScript")
    if gearSetsModule then
        local ok, value = pcall(requireModule, gearSetsModule)
        if ok and type(value) == "table" then gearSets = value end
    end
    local cityMapsModule = child(mw, "CityMaps", "ModuleScript")
    if cityMapsModule then
        local ok, value = pcall(requireModule, cityMapsModule)
        if ok and type(value) == "table" and type(value.BY_ID) == "table"
            and type(value.BY_NAME) == "table" then cityMaps = value end
    end
    if type(config) ~= "table" or type(config.COMBAT) ~= "table"
        or type(gameData) ~= "table" or type(gearSets) ~= "table"
        or type(gearSets.slotBonus) ~= "function" then
        return nil
    end
    local function optionalModule(name)
        local module = child(mw, name, "ModuleScript")
        if not module then return nil end
        local ok, value = pcall(requireModule, module)
        return ok and type(value) == "table" and value or nil
    end
    local util = optionalModule("Util")
    local territory = optionalModule("TerritoryBonusRules")
    local globalBuff = optionalModule("GlobalBuffKinds")
    local decree = optionalModule("DecreeRules")
    local serverClock = optionalModule("ServerClock")
    local bossStages = optionalModule("BossStages")
    local globalBossRules = optionalModule("GlobalBossRules")
    local seasonRules = optionalModule("SeasonRules")
    local seasonModule = child(mw, "SeasonRules", "ModuleScript")
    local currentTerritorySeason
    if seasonRules and seasonModule and type(seasonRules.status) == "function"
        and type(mw.GetAttribute) == "function" then
        local ok, http = pcall(function() return game:GetService("HttpService") end)
        if ok and http and type(http.JSONDecode) == "function" then
            local function currentSeason()
                if players.LocalPlayer ~= player or child(replicated, "MW", "Folder") ~= mw
                    or child(mw, "SeasonRules", "ModuleScript") ~= seasonModule then
                    error("Territory season source changed")
                end
            end
            currentTerritorySeason = {readLive = function()
                currentSeason()
                local encoded = mw:GetAttribute("SeasonLive")
                if encoded == nil then return nil end
                if type(encoded) ~= "string" or #encoded > 1048576 then error("Invalid native season attribute") end
                local decoded, value = pcall(http.JSONDecode, http, encoded)
                -- Match native TerritoryTopFamilies.seasonLive's nil calendar fallback.
                return decoded and type(value) == "table" and value or nil
            end, status = function(live, now)
                currentSeason()
                return seasonRules.status(live, now)
            end}
        end
    end
    local eventShop = optionalModule("EventShop")
    local currentEventShop
    local eventShopModule = child(mw, "EventShop", "ModuleScript")
    if eventShop and eventShopModule and serverClock and type(serverClock.now) == "function"
        and type(player.GetAttribute) == "function"
        and type(mw.GetAttribute) == "function" then
        currentEventShop = {definition = eventShop, readAttributes = function()
            if players.LocalPlayer ~= player or child(replicated, "MW", "Folder") ~= mw
                or child(mw, "EventShop", "ModuleScript") ~= eventShopModule then
                error("Event Shop attribute source changed")
            end
            local serverNow = serverClock.now()
            if type(serverNow) ~= "number" or serverNow ~= serverNow
                or serverNow < 0 or serverNow > 9007199254740991 then
                error("Native Event Shop clock unavailable")
            end
            return {GlobalEventShop = mw:GetAttribute("GlobalEventShop"),
                GlobalEventShopEnd = mw:GetAttribute("GlobalEventShopEnd"),
                MWPaidRandomRestricted = player:GetAttribute("MWPaidRandomRestricted"),
                serverNow = serverNow}
        end}
    end
    local currentBriefcases
    local briefcaseRules = optionalModule("BriefcaseRules")
    local briefcaseModule = child(mw, "BriefcaseRules", "ModuleScript")
    local clockModule = child(mw, "ServerClock", "ModuleScript")
    if game.PlaceVersion == 654 and briefcaseRules and briefcaseModule
        and serverClock and clockModule and type(serverClock.now) == "function"
        and type(mw.GetAttribute) == "function" then
        local readLatest, readNow = state.latest, serverClock.now
        local function currentCases()
            return game.PlaceVersion == 654 and players.LocalPlayer == player
                and child(scripts, "MWClient", "LocalScript") == client
                and child(client, "State", "ModuleScript") == stateModule and state.latest == readLatest
                and child(replicated, "MW", "Folder") == mw
                and child(mw, "BriefcaseRules", "ModuleScript") == briefcaseModule
                and child(mw, "ServerClock", "ModuleScript") == clockModule and serverClock.now == readNow
        end
        currentBriefcases = {definition = briefcaseRules, readCurrent = function()
            if not currentCases() then error("Native Briefcase source changed") end
            local data, now = readLatest(), readNow()
            if type(data) ~= "table" or not currentCases() then error("Native Briefcase state unavailable") end
            local result = {GlobalCaseEnd = mw:GetAttribute("GlobalCaseEnd"),
                GlobalCaseSeason = mw:GetAttribute("GlobalCaseSeason"), serverNow = now,
                briefcase = data.briefcase}
            if not currentCases() then error("Native Briefcase source changed during capture") end
            return result
        end}
    end
    local currentGlobalBoss
    if globalBossRules and type(globalBossRules.decode) == "function"
        and type(globalBossRules.canAccess) == "function"
        and globalBossRules.ATTR == "GlobalBossState" and globalBossRules.PRIVATE_ATTR == "GlobalBossPrivateState"
        and type(player.GetAttribute) == "function" and type(mw.GetAttribute) == "function" then
        currentGlobalBoss = {rule = globalBossRules, userId = player.UserId,
            readAttributes = function()
                if players.LocalPlayer ~= player or mw.Parent ~= replicated then
                    error("Global Boss attribute source changed")
                end
                return {GlobalBossPrivateState = player:GetAttribute("GlobalBossPrivateState"),
                    GlobalBossState = mw:GetAttribute("GlobalBossState")}
            end}
    end
    local currentShop
    local currentCrateLuck
    if territory and type(territory.fromData) == "function"
        and globalBuff and type(globalBuff.luck) == "function"
        and serverClock and type(serverClock.now) == "function" then
        local territoryModule = child(mw, "TerritoryBonusRules", "ModuleScript")
        local buffModule = child(mw, "GlobalBuffKinds", "ModuleScript")
        local clockModule = child(mw, "ServerClock", "ModuleScript")
        local fromData, globalLuck, now = territory.fromData, globalBuff.luck, serverClock.now
        currentCrateLuck = {crateLuck = function(native)
            if players.LocalPlayer ~= player or child(replicated, "MW", "Folder") ~= mw
                or child(mw, "TerritoryBonusRules", "ModuleScript") ~= territoryModule
                or child(mw, "GlobalBuffKinds", "ModuleScript") ~= buffModule
                or child(mw, "ServerClock", "ModuleScript") ~= clockModule
                or territory.fromData ~= fromData or globalBuff.luck ~= globalLuck
                or serverClock.now ~= now then error("Native crate luck source changed") end
            -- Same native crateLuck expression, using already bound modules:
            -- its nested require is unavailable from the executor's context.
            return fromData(native, "crateLuck") + globalLuck(mw, now())
        end}
    end
    if type(gameData.SHOP) == "table"
        and type(gameData.ITEMS_BY_ID) == "table"
        and util and type(util.shopStock) == "function"
        and type(util.shopPrice) == "function"
        and territory and type(territory.fromData) == "function"
        and type(territory.shopPrice) == "function"
        and globalBuff and type(globalBuff.sale) == "function"
        and decree and type(decree.pctFor) == "function"
        and serverClock and type(serverClock.now) == "function" then
        currentShop = { gameData = gameData, util = util,
            territory = territory, globalBuff = globalBuff,
            decree = decree, clock = serverClock, mw = mw }
    end
    -- Use the game's normal preflight/dialog path, never edit challenge state or submit picks.
    local marketPresence
    local presenceModule = child(client, "TerritoryPresence", "ModuleScript")
    if presenceModule then
        local ok, nativePresence = pcall(requireModule, presenceModule)
        if ok and type(nativePresence) == "table" and type(nativePresence.pending) == "function"
            and type(nativePresence.open) == "function" then
            local pending, open = nativePresence.pending, nativePresence.open
            local dialogShown = false
            local function current()
                return players.LocalPlayer == player and child(scripts, "MWClient", "LocalScript") == client
                    and child(client, "TerritoryPresence", "ModuleScript") == presenceModule
                    and nativePresence.pending == pending and nativePresence.open == open
            end
            local function dialog(payload)
                if not current() then return false, "Native Market check source changed" end
                local opened = pcall(open, payload, "market")
                return false, opened and "Complete the native Market check manually" or "Native Market dialog unavailable"
            end
            marketPresence = {
                check = function()
                    if not current() then return false, "Native Market check source changed" end
                    local read, blocked = pcall(pending, "market")
                    if not read or type(blocked) ~= "boolean" then return false, "Native Market preflight unavailable" end
                    if blocked then
                        if not dialogShown then dialogShown = true; return dialog(nil) end
                        return false, "Complete the native Market check manually"
                    end
                    dialogShown = false
                    return true, nil
                end,
                handle = function(reply)
                    if not current() then return false, "Native Market check source changed" end
                    if type(reply) ~= "table" then return false, "Native Market reply unavailable" end
                    if reply.code == "presence" then return dialog(reply.presence) end
                    return true, nil
                end,
            }
        end
    end
    -- Use the game's own wrapper; never read, store or reconstruct its validation value.
    local nativeRemoteLink
    local remoteLinkModule = child(client, "RemoteLink", "ModuleScript")
    if reviewedVersion(game.PlaceVersion) and not remoteLinkModule then return nil end
    if remoteLinkModule then
        local remoteLink = requireModule(remoteLinkModule)
        if type(remoteLink) ~= "table" or type(remoteLink.wrap) ~= "function" then return nil end
        local wrap = remoteLink.wrap
        local wrapped = wrap(remotes)
        if type(wrapped) ~= "table" or type(wrapped.FindFirstChild) ~= "function" then return nil end
        local lookup = wrapped.FindFirstChild
        local approved = {}
        for _, remote in ipairs(remotes:GetChildren()) do
            if remote:IsA("RemoteFunction") then
                local value = lookup(wrapped, remote.Name)
                if value == nil or value ~= remote and (type(value) ~= "table" or value.Instance ~= remote
                    or value.Name ~= remote.Name or type(value.InvokeServer) ~= "function") then return nil end
                approved[remote.Name] = {instance = remote, wrapper = value, invoke = value.InvokeServer}
            end
        end
        local rulesModule = child(mw, "ClientRules", "ModuleScript")
        local function currentLink()
            return players.LocalPlayer == player and child(scripts, "MWClient", "LocalScript") == client
                and child(client, "RemoteLink", "ModuleScript") == remoteLinkModule and remoteLink.wrap == wrap
                and child(replicated, "MW", "Folder") == mw and child(mw, "Remotes", "Folder") == remotes
                and child(mw, "ClientRules", "ModuleScript") == rulesModule
        end
        nativeRemoteLink = {Current = currentLink, Resolve = function(_, name)
            if not currentLink() or wrapped.FindFirstChild ~= lookup then error("Current native RemoteLink changed") end
            local expected = approved[name]
            local raw = child(remotes, name, "RemoteFunction")
            local value = lookup(wrapped, name)
            if not expected or expected.instance ~= raw or expected.wrapper ~= value
                or value.InvokeServer ~= expected.invoke then error("Current native wrapper binding changed") end
            return value
        end}
    end
    local currentFightNotifications
    local notify = child(remotes, "Notify", "RemoteEvent")
    if notify and notify.OnClientEvent and type(notify.OnClientEvent.Connect) == "function" then
        local function current()
            return players.LocalPlayer == player and child(scripts, "MWClient", "LocalScript") == client
                and child(client, "State", "ModuleScript") == stateModule
                and child(replicated, "MW", "Folder") == mw and child(mw, "Remotes", "Folder") == remotes
                and child(remotes, "Notify", "RemoteEvent") == notify
        end
        local fightModule, fight, attackFunction, remainingFunction, cooldownFunction
        local function nativeFunctions()
            if not current() or not reviewedVersion(game.PlaceVersion) or type(readUpvalues) ~= "function"
                or child(mw, "Config", "ModuleScript") ~= configModule then error("Native fight guard unavailable") end
            local module = child(client, "FightTab", "ModuleScript")
            if not module or fightModule and fightModule ~= module then error("Native FightTab changed") end
            if not fight then fightModule, fight = module, requireModule(module) end
            if type(fight) ~= "table" or type(fight.attack) ~= "function"
                or type(fight.attacksRemaining) ~= "function" or type(fight.cooldownLeft) ~= "function"
                or attackFunction and attackFunction ~= fight.attack
                or remainingFunction and remainingFunction ~= fight.attacksRemaining
                or cooldownFunction and cooldownFunction ~= fight.cooldownLeft then error("Native fight functions changed") end
            attackFunction, remainingFunction, cooldownFunction = fight.attack, fight.attacksRemaining, fight.cooldownLeft
            local up = readUpvalues(attackFunction)
            if type(up) ~= "table" or type(up[1]) ~= "function" or type(up[2]) ~= "table"
                or up[2].State ~= state or up[2].Config ~= config or type(up[3]) ~= "function"
                or type(up[5]) ~= "table" or type(up[5].warning) ~= "function"
                or type(up[7]) ~= "function" then error("Native fight context changed") end
            local busy = readUpvalues(up[1])
            if type(busy) ~= "table" or type(busy[1]) ~= "boolean" or busy[2] ~= up[2] then
                error("Native busy guard changed")
            end
            local attack = child(remotes, "Attack", "RemoteFunction")
            local linked = nativeRemoteLink and nativeRemoteLink:Resolve("Attack") or attack
            if not attack or linked == nil or up[2].Remotes.Attack ~= linked then error("Native Attack instance changed") end
            if linked ~= attack and (type(linked) ~= "table" or linked.Instance ~= attack
                or linked.Name ~= "Attack" or type(linked.InvokeServer) ~= "function") then error("Native Attack wrapper changed") end
            return up, busy
        end
        local function finite(value)
            return type(value) == "number" and value == value and value >= 0 and value <= 9007199254740991
        end
        local warSnapshot, warTarget, warAccept
        local function warAllowed(up, data, intent, target)
            local source, native = up[5], type(data.derived) == "table" and data.derived.war
            if type(source.snapshot) ~= "function" or type(source.targetOf) ~= "function"
                or warSnapshot and warSnapshot ~= source.snapshot or warTarget and warTarget ~= source.targetOf then return false end
            warSnapshot, warTarget = source.snapshot, source.targetOf
            local status, row = source.snapshot(), source.targetOf(target)
            local now, own = data.serverNow, type(data.family) == "table" and data.family.id
            local function integer(value, low) return finite(value) and value % 1 == 0 and value >= low end
            if not finite(now) or type(status) ~= "table" or not finite(status.serverNow)
                or math.abs(now - status.serverNow) > 10 or status.day ~= math.floor(now / 86400)
                or intent.warDay ~= status.day or not finite(intent.warStatusServerNow)
                or math.abs(now - intent.warStatusServerNow) > 10
                or type(native) ~= "table" or native.state ~= "active"
                or own == nil or own == 0 or own ~= intent.warOwnFamilyId
                or type(status.summary) ~= "table" or status.summary.canScore ~= true
                or not integer(status.summary.ownRemaining, 0) or not integer(status.summary.ownCap, 0)
                or status.summary.ownRemaining > status.summary.ownCap
                or status.summary.eligibleAt ~= nil and (not finite(status.summary.eligibleAt) or status.summary.eligibleAt > now)
                or type(status.targets) ~= "table" or #status.targets > 128 then return false end
            local enemy = status.summary.enemyId or (status.targets[1] and status.targets[1].familyId)
            if enemy ~= intent.warEnemyFamilyId or enemy ~= intent.familyId or enemy == own
                or type(enemy) ~= type(own) or native.enemyId ~= nil and native.enemyId ~= enemy
                or type(row) ~= "table" or row.userId ~= target or row.familyId ~= enemy
                or row.name ~= intent.targetName or row.level ~= intent.targetLevel then return false end
            local found, seen, count = false, {}, 0
            for key, item in pairs(status.targets) do
                count = count + 1
                if not integer(key, 1) or key > #status.targets or type(item) ~= "table"
                    or not integer(item.userId, 1) or seen[item.userId] or item.familyId ~= enemy then return false end
                seen[item.userId] = true
                if item == row then found = true end
            end
            local allowance = row.warStatus
            return found and count == #status.targets and type(allowance) == "table"
                and allowance.day == status.day and allowance.canScore == true
                and integer(allowance.remaining, 1) and integer(allowance.cap, 1) and allowance.remaining <= allowance.cap
                and integer(allowance.attacksRemaining, 1) and integer(allowance.attacksCap, 1)
                and allowance.attacksRemaining <= allowance.attacksCap and integer(allowance.pairRemaining, 1)
        end
        local function acceptWarStatus(raw, expected)
            local up = nativeFunctions()
            local source, data = up[5], state.latest()
            local function scopeEqual(a, b)
                if type(a) ~= "table" or type(b) ~= "table" or a.serverNow ~= b.serverNow then return false end
                local af, bf = type(a.family) == "table" and a.family.id, type(b.family) == "table" and b.family.id
                local aw = type(a.derived) == "table" and a.derived.war
                local bw = type(b.derived) == "table" and b.derived.war
                return af == bf and type(aw) == type(bw)
                    and (type(aw) ~= "table" or aw.state == bw.state and aw.enemyId == bw.enemyId)
            end
            if not scopeEqual(data, expected) or expected.fullSync ~= true or not finite(data.serverNow)
                or type(source.accept) ~= "function" or type(source.snapshot) ~= "function"
                or type(source.targetOf) ~= "function" or warAccept and warAccept ~= source.accept
                or warSnapshot and warSnapshot ~= source.snapshot or warTarget and warTarget ~= source.targetOf then return false end
            warAccept, warSnapshot, warTarget = source.accept, source.snapshot, source.targetOf
            local nodes, bytes, seen = 0, 0, {}
            local function copy(value, depth)
                nodes = nodes + 1
                if nodes > 8192 or depth > 8 then error("War cache payload exceeds bounds") end
                local kind = type(value)
                if kind == "string" then
                    bytes = bytes + #value
                    if #value > 8192 or bytes > 262144 then error("War cache strings exceed bounds") end
                elseif kind == "number" then
                    if value ~= value or math.abs(value) > 9007199254740991 then error("Invalid war cache number") end
                elseif kind ~= "table" and kind ~= "boolean" and kind ~= "nil" then error("Invalid war cache value") end
                if kind ~= "table" then return value end
                if seen[value] or getmetatable(value) ~= nil then error("Invalid war cache graph") end
                seen[value] = true
                local out = {}
                for key, childValue in pairs(value) do
                    if type(key) ~= "string" and type(key) ~= "number" then error("Invalid war cache key") end
                    out[copy(key, depth + 1)] = copy(childValue, depth + 1)
                end
                seen[value] = nil
                return out
            end
            local payload = copy(raw, 0)
            if type(payload) ~= "table" or not finite(payload.serverNow) or math.abs(data.serverNow - payload.serverNow) > 10
                or payload.day ~= math.floor(payload.serverNow / 86400) or payload.day ~= math.floor(data.serverNow / 86400)
                or type(payload.targets) ~= "table" or #payload.targets > 128 then return false end
            local count, ids = 0, {}
            local nativeWar = type(data.derived) == "table" and data.derived.war
            local active = type(nativeWar) == "table" and nativeWar.state == "active"
            local enemy = type(payload.summary) == "table" and (payload.summary.enemyId or (payload.targets[1] and payload.targets[1].familyId))
            local function integer(value, low) return finite(value) and value % 1 == 0 and value >= low end
            if type(payload.summary) == "table" then
                local summary = payload.summary
                if type(summary.canScore) ~= "boolean" or not integer(summary.ownRemaining, 0) or not integer(summary.ownCap, 0)
                    or summary.ownRemaining > summary.ownCap
                    or summary.eligibleAt ~= nil and not finite(summary.eligibleAt) then return false end
            end
            for key, row in pairs(payload.targets) do
                count = count + 1
                if not finite(key) or key % 1 ~= 0 or key < 1 or key > #payload.targets or type(row) ~= "table"
                    or not integer(row.userId, 1) or ids[row.userId] or not integer(row.level, 1)
                    or type(row.name) ~= "string" or #row.name < 1 or #row.name > 64 or row.name:find("[%c]")
                    or active and row.familyId ~= enemy then return false end
                local allowance = row.warStatus
                if type(allowance) ~= "table" or allowance.day ~= payload.day or type(allowance.canScore) ~= "boolean"
                    or not integer(allowance.remaining, 0) or not integer(allowance.cap, 0) or allowance.remaining > allowance.cap
                    or not integer(allowance.attacksRemaining, 0) or not integer(allowance.attacksCap, 0)
                    or allowance.attacksRemaining > allowance.attacksCap or not integer(allowance.pairRemaining, 0) then return false end
                ids[row.userId] = true
            end
            if count ~= #payload.targets or active and (type(payload.summary) ~= "table" or enemy == nil
                    or type(data.family) ~= "table" or enemy == data.family.id or type(enemy) ~= type(data.family.id)
                    or nativeWar.enemyId ~= nil and nativeWar.enemyId ~= enemy)
                or not active and (payload.summary ~= nil or count ~= 0) then return false end
            if not scopeEqual(state.latest(), expected) then return false end
            local accepted = warAccept(payload)
            local latestUp = nativeFunctions()
            return accepted == true and latestUp[5] == source and source.accept == warAccept
                and source.snapshot == warSnapshot and source.targetOf == warTarget
                and scopeEqual(state.latest(), expected) and source.snapshot() == payload
        end
        local function canAttack(proposal, target)
            if type(proposal) ~= "table" or (proposal.feature ~= "combat" and proposal.feature ~= "warCombat")
                or type(proposal.intent) ~= "table" or proposal.intent.kind ~= "playerAttack"
                or proposal.intent.target ~= target or not finite(target) or target % 1 ~= 0 or target < 1
                or target == player.UserId or type(proposal.resources) ~= "table" then
                return false, "Exact ordinary player attack required"
            end
            local up, busy = nativeFunctions()
            local data = state.latest()
            local pools = type(data) == "table" and data.pools
            local rules = config.COMBAT
            if busy[1] ~= false or not finite(busy[5]) or busy[5] > os.clock()
                or not finite(up[4]) or up[4] > os.time()
                or type(pools) ~= "table" or not finite(pools.health) or not finite(pools.stamina)
                or not finite(rules.hospitalHealth) or not finite(rules.staminaCost) or rules.staminaCost < 1
                or rules.staminaCost > 5 or rules.staminaCost % 1 ~= 0
                or not finite(rules.bullyMaxStamina) or rules.bullyMaxStamina < rules.staminaCost
                or rules.bullyMaxStamina > 5 or rules.bullyMaxStamina % 1 ~= 0
                or proposal.intent.maxStaminaExposure ~= rules.bullyMaxStamina
                or proposal.resources.stamina ~= proposal.intent.maxStaminaExposure
                or not finite(proposal.intent.expectedStaminaCost) or proposal.intent.expectedStaminaCost % 1 ~= 0
                or proposal.intent.expectedStaminaCost < rules.staminaCost or proposal.intent.expectedStaminaCost > rules.bullyMaxStamina
                or not finite(proposal.intent.staminaReserve) or proposal.intent.staminaReserve % 1 ~= 0
                or not finite(proposal.intent.uncertainStamina) or not finite(proposal.intent.healthFloor)
                or proposal.intent.healthFloor < 1 or proposal.intent.healthFloor > 100
                or type(data.stats) ~= "table" or not finite(data.stats.maxHealth) or data.stats.maxHealth < 1
                or pools.health < math.max(rules.hospitalHealth, data.stats.maxHealth * proposal.intent.healthFloor / 100)
                or pools.stamina < proposal.resources.stamina + proposal.intent.staminaReserve + proposal.intent.uncertainStamina
                or not finite(data.serverNow) or not finite(data.shieldUntil)
                or data.shieldUntil > data.serverNow then return false, "Native busy, shield or resource guard" end
            local row = {userId = target, familyId = proposal.intent.familyId}
            local validFamily = type(row.familyId) == "string" and #row.familyId <= 120 or row.familyId == 0
            if proposal.feature == "warCombat" then
                validFamily = (type(row.familyId) == "string" and #row.familyId > 0 and #row.familyId <= 120
                    and not row.familyId:find("[%c]") or finite(row.familyId) and row.familyId % 1 == 0 and row.familyId >= 1)
                    and warAllowed(up, data, proposal.intent, target)
            end
            if not validFamily
                or up[3](row) ~= false or up[5].warning(target) ~= nil then
                return false, "Native Family or war warning requires manual handling"
            end
            local remaining, cooldown = fight.attacksRemaining(target), fight.cooldownLeft(target)
            if not finite(remaining) or remaining % 1 ~= 0 or remaining < 1
                or not finite(cooldown) or cooldown > 0 then return false, "Native target limit or cooldown" end
            return true, nil
        end
        local profileModule, profile, profileOpen
        local function canScout(proposal, target)
            local intent = type(proposal) == "table" and proposal.intent
            local rules = config.COMBAT
            if type(intent) ~= "table" or intent.kind ~= "playerScout" or intent.allowScout ~= true
                or not finite(rules.scoutStaminaCost) or rules.scoutStaminaCost < 1
                or rules.scoutStaminaCost > 5 or rules.scoutStaminaCost % 1 ~= 0
                or intent.expectedStaminaCost ~= rules.scoutStaminaCost
                or intent.attackExposure ~= rules.bullyMaxStamina then
                return false, "Explicit Scout quote and follow-up attack reserve required"
            end
            -- Reuse the stricter ordinary attack safeguards without altering the caller's intent.
            local attack = {}
            for key, value in pairs(proposal) do attack[key] = value end
            attack.intent = {}
            for key, value in pairs(intent) do attack.intent[key] = value end
            attack.intent.kind = "playerAttack"
            attack.intent.expectedStaminaCost = rules.staminaCost
            local module = child(client, "ProfilePopup", "ModuleScript")
            if not module or profileModule and profileModule ~= module then return false, "Native Scout source changed" end
            if not profile then profileModule, profile = module, requireModule(module) end
            if type(profile) ~= "table" or type(profile.open) ~= "function"
                or profileOpen and profileOpen ~= profile.open then return false, "Native Scout function changed" end
            profileOpen = profile.open
            -- Read the native context/busy state; never call open or modify its flags.
            local permitted, why = canAttack(attack, target)
            if not permitted then return false, why end
            local up = readUpvalues(profileOpen)
            local raw = child(remotes, "ScoutPlayer", "RemoteFunction")
            local linked = nativeRemoteLink and nativeRemoteLink:Resolve("ScoutPlayer") or nil
            if type(up) ~= "table" or up[3] ~= false or type(up[5]) ~= "table"
                or up[5].State ~= state or up[5].Config ~= config or type(up[5].Remotes) ~= "table"
                or not raw or type(linked) ~= "table" or linked.Instance ~= raw or linked.Name ~= "ScoutPlayer"
                or type(linked.InvokeServer) ~= "function" or up[5].Remotes.ScoutPlayer ~= linked then
                return false, "Native Scout busy or context changed"
            end
            local data = state.latest()
            if type(data) ~= "table" or type(data.pools) ~= "table" or not finite(data.pools.stamina)
                or data.pools.stamina < proposal.resources.stamina + intent.attackExposure
                    + intent.staminaReserve + intent.uncertainStamina then
                return false, "Scout and follow-up attack Stamina reserve"
            end
            return true, nil
        end
        local prestigeMultiplier = type(config) == "table" and config.prestigeMult
        local skillMultiplier = type(config) == "table" and config.skillPowerMult
        local function combatFrame(native, targets)
            local up, busy = nativeFunctions()
            local rules = config.COMBAT
            local stats = type(native) == "table" and native.stats
            local derived = type(native) == "table" and (native.derived or {})
            local pools = type(native) == "table" and native.pools
            if type(native) ~= "table" or native.fullSync ~= true or not finite(native.serverNow)
                or not finite(native.shieldUntil) or type(stats) ~= "table" or not finite(stats.atkBase)
                or not finite(stats.maxHealth) or stats.maxHealth < 1 or type(derived) ~= "table"
                or not finite(derived.gearAtk or 0) or not finite(derived.crewBonus or 0)
                or type(pools) ~= "table" or not finite(pools.health) or not finite(pools.stamina)
                or pools.health > stats.maxHealth or not finite(up[4]) or not finite(busy[5])
                or type(prestigeMultiplier) ~= "function" or type(skillMultiplier) ~= "function"
                or config.prestigeMult ~= prestigeMultiplier or config.skillPowerMult ~= skillMultiplier
                or not finite(rules.hospitalHealth) or rules.hospitalHealth < 1
                or not finite(rules.staminaCost) or rules.staminaCost < 1 or rules.staminaCost > 5 or rules.staminaCost % 1 ~= 0
                or not finite(rules.targetCooldown)
                or not finite(rules.scoutStaminaCost) or rules.scoutStaminaCost < 1 or rules.scoutStaminaCost > 5
                or rules.scoutStaminaCost % 1 ~= 0 or not finite(rules.bullyMaxStamina)
                or rules.bullyMaxStamina < 1 or rules.bullyMaxStamina > 5 or rules.bullyMaxStamina % 1 ~= 0
                or not finite(rules.fightVariance) or not finite(rules.fightVarianceCap)
                or not finite(rules.dailyTargetCap) or rules.dailyTargetCap % 1 ~= 0
                or type(targets) ~= "table" or #targets > 128 then return nil end
            local familyId = 0
            if native.family ~= nil then
                if type(native.family) ~= "table" then return nil end
                familyId = native.family.id
                if not (type(familyId) == "string" and #familyId > 0 and #familyId <= 120
                    and not familyId:find("[%c]") or finite(familyId) and familyId % 1 == 0 and familyId >= 1) then return nil end
            end
            local pm, sm = prestigeMultiplier(native), skillMultiplier(native, "attack")
            if not finite(pm) or pm <= 0 or not finite(sm) or sm <= 0 then return nil end
            -- Current native FightTab.myExpectedPower source; an estimate, not a server-roll guarantee.
            local attack = math.max(10, (stats.atkBase + (derived.gearAtk or 0))
                * (1 + (derived.crewBonus or 0)) * pm * sm)
            if not finite(attack) then return nil end
            local out = {ownUserId = player.UserId, ownFamilyId = familyId, attack = attack,
                health = pools.health, maxHealth = stats.maxHealth, stamina = pools.stamina,
                hospitalHealth = rules.hospitalHealth, staminaCost = rules.staminaCost, scoutCost = rules.scoutStaminaCost,
                targetCooldown = rules.targetCooldown,
                maxStaminaCost = rules.bullyMaxStamina, dailyTargetCap = rules.dailyTargetCap,
                fightVariance = rules.fightVariance, fightVarianceCap = rules.fightVarianceCap,
                busy = busy[1], globalCooldown = math.max(0, busy[5] - os.clock()),
                shielded = up[4] > os.time() or native.shieldUntil > native.serverNow, targets = {}}
            local count = 0
            for key in pairs(targets) do
                if not finite(key) or key % 1 ~= 0 or key < 1 or key > #targets then return nil end
                count = count + 1
            end
            if count ~= #targets then return nil end
            for _, row in ipairs(targets) do
                local id = type(row) == "table" and row.userId
                if not finite(id) or id < 1 or id % 1 ~= 0 or out.targets[tostring(id)] then return nil end
                local remaining, cooldown, same = fight.attacksRemaining(id), fight.cooldownLeft(id), up[3](row)
                if not finite(remaining) or remaining % 1 ~= 0 or not finite(cooldown) or type(same) ~= "boolean" then return nil end
                out.targets[tostring(id)] = {remainingDaily = remaining, cooldownLeft = cooldown,
                    sameFamily = same, manualWarning = up[5].warning(id) ~= nil}
            end
            local latestUp, latestBusy = nativeFunctions()
            if not current() or config.prestigeMult ~= prestigeMultiplier or config.skillPowerMult ~= skillMultiplier
                or latestUp[4] ~= up[4] or latestBusy[1] ~= busy[1] or latestBusy[5] ~= busy[5] then return nil end
            return out
        end
        local function friendshipMethod()
            local ok, value = pcall(function() return player.IsFriendsWithAsync end)
            return ok and type(value) == "function" and value or nil
        end
        local isFriends = friendshipMethod()
        currentFightNotifications = {Current = current, AcceptWarStatus = function(_, raw, expected)
            local ok, accepted = pcall(acceptWarStatus, raw, expected)
            return ok and accepted == true
        end, CombatFrame = function(_, native, targets)
            local ok, value = pcall(combatFrame, native, targets)
            return ok and value or nil
        end, Friendship = function(_, target)
            if not current() or not isFriends or friendshipMethod() ~= isFriends
                or not finite(target) or target < 1 or target % 1 ~= 0 or target == player.UserId then return nil end
            -- Roblox documents cached results. A successful false is reported,
            -- never described as an uncached real-time friendship guarantee.
            local ok, value = pcall(isFriends, player, target)
            if not ok or type(value) ~= "boolean" or not current() or friendshipMethod() ~= isFriends then return nil end
            return value
        end, Subscribe = function(_, callback)
            if not current() then error("Current fight notifications changed") end
            return notify.OnClientEvent:Connect(callback)
        end, CanAttack = function(_, proposal, target)
            local ok, accepted, why = pcall(canAttack, proposal, target)
            return ok and accepted == true, ok and why or "Current native fight preflight unavailable"
        end, CanScout = function(_, proposal, target)
            local ok, accepted, why = pcall(canScout, proposal, target)
            return ok and accepted == true, ok and why or "Current native Scout preflight unavailable"
        end, HandleReply = function(_, reply)
            if type(reply) ~= "table" or not current() then return false end
            if reply.ok ~= false then return true end
            local ok = pcall(function()
                local up = nativeFunctions()
                local perform = readUpvalues(up[7])
                if type(perform) ~= "table" or type(perform[14]) ~= "function" then error("Native feedback unavailable") end
                local feedback = {}
                for key, value in pairs(reply) do feedback[key] = value end
                perform[14](reply.code == "target_hospitalized" and "hospitalized" or "error",
                    reply.msg or "The attack could not be resolved. Try again.", feedback)
            end)
            return ok
        end}
    end
    -- Own-player display facts only. No profile RPC, private state or trust-score inference.
    local incomeFunction = config.fightIncomeMult
    local propertyRows = gameData.PROPERTIES
    local function playerInfoCurrent()
        return reviewedVersion(game.PlaceVersion) and players.LocalPlayer == player
            and child(scripts, "MWClient", "LocalScript") == client
            and child(client, "State", "ModuleScript") == stateModule
            and child(replicated, "MW", "Folder") == mw
            and child(mw, "Config", "ModuleScript") == configModule
            and child(mw, "GameData", "ModuleScript") == gameDataModule
            and config.fightIncomeMult == incomeFunction and gameData.PROPERTIES == propertyRows
    end
    local currentPlayerInfo = {Current = playerInfoCurrent, Read = function(_, native)
        if not playerInfoCurrent() or type(native) ~= "table" or native.userId ~= player.UserId
            or type(native.serverNow) ~= "number" or native.serverNow ~= native.serverNow
            or native.serverNow < 0 or native.serverNow == math.huge then return nil end
        local out = {userId = player.UserId, name = player.Name, displayName = player.DisplayName}
        if type(incomeFunction) == "function" then
            -- Exact current PropsTab display path: derived income * fightIncomeMult.
            local ok, mult = pcall(incomeFunction, native.raidDebuff, native.winStreak, native.serverNow)
            if ok and type(mult) == "number" and mult == mult and mult >= 0 and mult < math.huge then out.propertyMultiplier = mult end
        end
        if type(propertyRows) == "table" and #propertyRows <= 256 then
            local rows, seen, valid, count = {}, {}, true, 0
            for k in pairs(propertyRows) do
                if type(k) ~= "number" or k % 1 ~= 0 or k < 1 or k > #propertyRows then valid = false end
                count = count + 1
            end
            for _, row in ipairs(propertyRows) do
                if type(row) ~= "table" or type(row.id) ~= "string" or #row.id < 1 or #row.id > 120
                    or seen[row.id] or type(row.name) ~= "string" or #row.name < 1 or #row.name > 120
                    or row.name:find("[%c]") then valid = false; break end
                local income = row.incomePerHour
                if income == nil and type(row.goldPerDay) == "number" and row.goldPerDay == row.goldPerDay
                    and row.goldPerDay >= 0 and row.goldPerDay < math.huge then income = 0 end
                if type(income) ~= "number" or income ~= income or income < 0 or income == math.huge then valid = false; break end
                seen[row.id] = true
                rows[#rows + 1] = {id = row.id, name = row.name, incomePerHour = income,
                    goldPerDay = type(row.goldPerDay) == "number" and row.goldPerDay == row.goldPerDay
                        and row.goldPerDay >= 0 and row.goldPerDay < math.huge and row.goldPerDay or nil}
            end
            if valid and count == #propertyRows then out.properties = rows end
        end
        return playerInfoCurrent() and out or nil
    end}
    local currentPrestigeController
    if type(readUpvalues) == "function" and nativeRemoteLink then
        local ok, source = pcall(function()
            local placeVersion = game.PlaceVersion -- Capture only an explicitly reviewed contract before yielding requires.
            if game.PlaceId ~= 73897506680154 or not reviewedVersion(placeVersion) then return nil end
            local modalModule = child(client, "PrestigeModal", "ModuleScript")
            local fightModule = child(client, "FightTab", "ModuleScript")
            local rulesModule = child(mw, "Prestige", "ModuleScript")
            local remote = child(remotes, "PrestigeAction", "RemoteFunction")
            if not modalModule or not fightModule or not rulesModule or not remote then return nil end
            local modalApi, fightApi, rules = requireModule(modalModule), requireModule(fightModule), requireModule(rulesModule)
            if type(modalApi) ~= "table" or type(modalApi.open) ~= "function" or type(modalApi.init) ~= "function"
                or type(fightApi) ~= "table" or type(fightApi.confirm) ~= "function" or type(rules) ~= "table"
                or type(rules.canPrestige) ~= "function" or type(rules.rankOf) ~= "function" then return nil end
            if game.PlaceId ~= 73897506680154 or game.PlaceVersion ~= placeVersion then return nil end
            local init, open, confirm = modalApi.init, modalApi.open, fightApi.confirm
            local first, shown, confirmation = readUpvalues(init), readUpvalues(open), readUpvalues(confirm)
            if type(first) ~= "table" or type(shown) ~= "table" or type(confirmation) ~= "table" then return nil end
            local ctx, root, modal = first[1], first[2], first[3]
            if type(ctx) ~= "table" or not root or not modal or type(first[4]) ~= "function"
                or type(first[7]) ~= "function" or type(first[8]) ~= "function" then return nil end
            local gui, confirmationModal = ctx.gui, child(root, "ConfirmModal", "Frame")
            if not confirmationModal then return nil end
            local canPrestige, rankOf, latest = rules.canPrestige, rules.rankOf, state.latest
            local linked = nativeRemoteLink:Resolve("PrestigeAction")
            if type(linked) ~= "table" or linked.Instance ~= remote or linked.Name ~= "PrestigeAction"
                or type(linked.InvokeServer) ~= "function" then return nil end
            local invoke, close, any, paint = linked.InvokeServer, first[4], first[7], first[8]
            local retired, closed = false, false
            local function observe()
                if closed or retired or game.PlaceId ~= 73897506680154 or game.PlaceVersion ~= placeVersion
                    or players.LocalPlayer ~= player or child(scripts, "MWClient", "LocalScript") ~= client
                    or child(client, "State", "ModuleScript") ~= stateModule or state.latest ~= latest
                    or child(client, "PrestigeModal", "ModuleScript") ~= modalModule
                    or child(client, "FightTab", "ModuleScript") ~= fightModule or child(mw, "Prestige", "ModuleScript") ~= rulesModule
                    or child(mw, "Config", "ModuleScript") ~= configModule or modalApi.init ~= init or modalApi.open ~= open
                    or fightApi.confirm ~= confirm or rules.canPrestige ~= canPrestige or rules.rankOf ~= rankOf then return nil end
                local i, o, c = readUpvalues(init), readUpvalues(open), readUpvalues(confirm)
                if type(i) ~= "table" or type(o) ~= "table" or type(c) ~= "table" or i[1] ~= ctx or i[2] ~= root or i[3] ~= modal
                    or i[4] ~= close or i[6] ~= rules or i[7] ~= any or i[8] ~= paint or type(i[5]) ~= "boolean"
                    or o[1] ~= ctx or o[2] ~= rules or o[3] ~= paint or o[4] ~= root or o[5] ~= modal
                    or c[1] ~= root or c[4] ~= ctx or c[3] ~= nil and type(c[3]) ~= "function"
                    or ctx.State ~= state or ctx.Config ~= config or ctx.confirmDialog ~= confirm or ctx.player ~= player or ctx.gui ~= gui
                    or child(player, "PlayerGui", "PlayerGui") ~= gui.Parent
                    or child(gui.Parent, gui.Name, "ScreenGui") ~= gui or child(child(gui, "Root", "Frame"), "Modals", "Frame") ~= root
                    or child(root, "PrestigeModal", "Frame") ~= modal or child(root, "ConfirmModal", "Frame") ~= confirmationModal
                    or type(root.Visible) ~= "boolean" or type(ctx.Remotes) ~= "table" or ctx.Remotes.PrestigeAction ~= linked
                    or not nativeRemoteLink:Current() or nativeRemoteLink:Resolve("PrestigeAction") ~= linked
                    or linked.InvokeServer ~= invoke or linked.Instance ~= remote or linked.Name ~= "PrestigeAction"
                    or child(remotes, "PrestigeAction", "RemoteFunction") ~= remote then return nil end
                local children = root:GetChildren()
                if type(children) ~= "table" or #children > 128 then return nil end
                local visible = root.Visible
                for _, row in ipairs(children) do
                    if row.Name ~= "Backdrop" and row:IsA("GuiObject") then
                        if type(row.Visible) ~= "boolean" then return nil end
                        visible = visible or row.Visible
                    end
                end
                return {busy = i[5], confirmationPending = c[3] ~= nil, modalOpen = visible}
            end
            local function current()
                local success, value = pcall(observe)
                if not success or value == nil then retired = true; return nil end
                return value
            end
            return {Current = function() return current() ~= nil end, Close = function() closed = true end,
                Read = function()
                    local flags = current()
                    if not flags then return nil end
                    local success, value = pcall(function()
                        local data = latest()
                        if type(data) ~= "table" or data.userId ~= nil and data.userId ~= player.UserId then return nil end
                        local level, xp = data.level, data.xp
                        local rank, ready = rankOf(data), canPrestige(data)
                        local function integer(v, low, high)
                            return type(v) == "number" and v == v and v % 1 == 0 and v >= low and v <= high
                        end
                        if not integer(rank, 0, 6) or not integer(data.level, 1, 9007199254740991)
                            or type(data.xp) ~= "number" or data.xp ~= data.xp or data.xp < 0 or data.xp > 9007199254740991
                            or type(ready) ~= "boolean" then return nil end
                        local post = latest()
                        if type(post) ~= "table" then return nil end
                        local postRank = rankOf(post)
                        if post.userId ~= nil and post.userId ~= player.UserId or post.level ~= level or post.xp ~= xp
                            or postRank ~= rank then return nil end
                        return {rank = rank, level = level, xp = xp, ready = ready}
                    end)
                    local after = current()
                    if not success or not value or not after or after.busy ~= flags.busy
                        or after.confirmationPending ~= flags.confirmationPending or after.modalOpen ~= flags.modalOpen then return nil end
                    value.busy, value.confirmationPending, value.modalOpen = flags.busy, flags.confirmationPending, flags.modalOpen
                    value.controllersClear = not flags.busy and not flags.confirmationPending and not flags.modalOpen
                    return value
                end}
        end)
        if ok then currentPrestigeController = source end
    end
    local currentHeistController
    if type(heistControllerModule) == "table" and type(heistControllerModule.bind) == "function" then
        currentHeistController = heistControllerModule.bind(game, requireModule, readUpvalues)
    end
    local currentRecallController
    if type(recallControllerModule) == "table" and type(recallControllerModule.bind) == "function" then
        currentRecallController = recallControllerModule.bind(game, requireModule, readUpvalues)
    end
    local currentFamilyBossController
    if type(familyBossControllerModule) == "table" and type(familyBossControllerModule.bind) == "function" then
        currentFamilyBossController = familyBossControllerModule.bind(game, requireModule, readUpvalues)
    end
    local groupLookup
    if type(player.IsInGroup) == "function" then
        groupLookup = function(groupId)
            return player:IsInGroup(groupId)
        end
    end
    return { moduleFolder = mw, remotesFolder = remotes,
        userId = player.UserId,
        uiParent = child(player, "PlayerGui", "PlayerGui"),
        nativeState = state, stateModule = stateModule,
        currentDailyBuffRules = dailyBuffRules,
        config = config, gameData = gameData, cityMaps = cityMaps,
        gearSets = gearSets, combatRules = config.COMBAT,
        groupLookup = groupLookup, currentShop = currentShop,
        marketPresence = marketPresence,
        bossStages = bossStages,
        currentGlobalBoss = currentGlobalBoss,
        currentFightNotifications = currentFightNotifications, currentPrestigeController = currentPrestigeController,
        nativeRemoteLink = nativeRemoteLink, currentPlayerInfo = currentPlayerInfo,
        currentHeistController = currentHeistController,
        currentRecallController = currentRecallController,
        currentFamilyBossController = currentFamilyBossController,
        currentEventShop = currentEventShop,
        currentBriefcases = currentBriefcases,
        currentTerritorySeason = currentTerritorySeason,
        currentCrateLuck = currentCrateLuck }
end

function NativeClientBindings.read(game, requireModule, readUpvalues, heistControllerModule, recallControllerModule, familyBossControllerModule)
    if game == nil or type(requireModule) ~= "function" then
        return nil, "Missing current-client bindings"
    end
    local ok, result = pcall(resolve, game, requireModule, readUpvalues, heistControllerModule, recallControllerModule, familyBossControllerModule)
    if not ok or result == nil then
        return nil, "Current MWClient State or Remotes unavailable"
    end
    return result, nil
end

return NativeClientBindings
