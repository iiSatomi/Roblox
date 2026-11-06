-- Add the verified combat/profile boundary to the native client fixture.
return function(f)
    for _, name in ipairs({"Attack", "ScoutPlayer"}) do
        local remote = f.remotes:Add(f.node(name, "RemoteFunction"))
        f.wrapped[name] = {Name = name, Instance = remote,
            InvokeServer = function() error("Read-only preflight must not invoke a remote") end}
    end
    local notify = f.remotes:Add(f.node("Notify", "RemoteEvent"))
    notify.OnClientEvent = {Connect = function()
        return {Disconnect = function() end}
    end}
    f.config.COMBAT = {hospitalHealth = 20, staminaCost = 1,
        scoutStaminaCost = 1, bullyMaxStamina = 5, targetCooldown = 30,
        dailyTargetCap = 5, fightVariance = 0.2, fightVarianceCap = 5000}
    f.config.prestigeMult = function() return 1.1 end
    f.config.skillPowerMult = function(_, kind)
        assert(kind == "attack")
        return 1.2
    end
    f.config.fightIncomeMult = function(_, _, now)
        assert(now == 100)
        return 0.9
    end
    f.gameData.PROPERTIES = {{id = "p_a", name = "Property A", incomePerHour = 100}}
    f.player.DisplayName = "User A"
    function f.player:IsFriendsWithAsync(id) return id == 789 end
    f.data.fullSync, f.data.serverNow, f.data.shieldUntil = true, 100, 0
    f.data.stats = {atkBase = 40, maxHealth = 100}
    f.data.pools = {health = 100, stamina = 20}
    f.data.derived = {gearAtk = 10, crewBonus = 0.1}
    local function attack() end
    local function attackBlocked() end
    local function perform() end
    f.fightApi.attack = attack
    f.fightApi.attacksRemaining = function() return 5 end
    f.fightApi.cooldownLeft = function() return 0 end
    local war = {warning = function() return nil end}
    local family = function() return false end
    f.attack = {attackBlocked, f.ctx, family, 0, war, f.fightApi.confirm, perform}
    f.busy = {false, f.ctx, nil, nil, 0}
    f.upvalues[attack], f.upvalues[attackBlocked] = f.attack, f.busy
    f.upvalues[perform] = {[14] = function() end}
    local function open() end
    f.profile = {open = open}
    f.profileUpvalues = {0, nil, false, nil, f.ctx}
    f.upvalues[open] = f.profileUpvalues
    f.client:Add(f.node("ProfilePopup", "ModuleScript")).Value = f.profile
    f.proposal = {feature = "combat", resources = {stamina = 5}, intent = {
        kind = "playerAttack", target = 456, familyId = 0,
        maxStaminaExposure = 5, expectedStaminaCost = 1,
        staminaReserve = 0, uncertainStamina = 0, healthFloor = 20,
    }}
    return f
end
