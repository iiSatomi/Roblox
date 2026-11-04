-- Explicit opt-in owner for the App, native events and quarter-second loop.
local RuntimeHost = {}

local function disconnect(handles)
    for _, handle in ipairs(handles) do
        pcall(handle.Disconnect, handle)
    end
end

local function disconnectable(handle)
    local ok, method = pcall(function()
        return handle.Disconnect
    end)
    return ok and type(method) == "function"
end

function RuntimeHost.start(deps)
    local currentClient = type(deps) == "table"
        and deps.activateCurrentClient == true
    if type(deps) ~= "table" or deps.activateRuntimeHost ~= true
        or deps.activateAutomation ~= true
        or deps.activateStorage ~= true
        or type(deps.App) ~= "table"
        or type(deps.App.start) ~= "function"
        or type(deps.NativeSnapshotReader) ~= "table"
        or type(deps.NativeSnapshotReader.new) ~= "function"
        or type(deps.RuntimeDriver) ~= "table"
        or type(deps.RuntimeDriver.new) ~= "function"
        or type(deps.RuntimeLoop) ~= "table"
        or type(deps.RuntimeLoop.new) ~= "function"
        or type(deps.NativeCallPlan) ~= "table"
        or type(deps.NativeCallPlan.describe) ~= "function"
        or type(deps.NativeCallPlan.withCrew) ~= "function"
        or type(deps.NativeCallPlan.withInventory) ~= "function"
        or type(deps.NativeCallPlan.withCollection) ~= "function"
        or type(deps.NativeCallPlan.withCombat) ~= "function"
        or type(deps.NativeCallPlan.withMarket) ~= "function"
        or type(deps.CrewCallPlan) ~= "table"
        or type(deps.CrewCallPlan.describe) ~= "function"
        or type(deps.InventoryCallPlan) ~= "table"
        or type(deps.InventoryCallPlan.describe) ~= "function"
        or type(deps.CollectionCallPlan) ~= "table"
        or type(deps.CollectionCallPlan.describe) ~= "function"
        or type(deps.CombatCallPlan) ~= "table"
        or type(deps.CombatCallPlan.describe) ~= "function"
        or type(deps.MarketCallPlan) ~= "table"
        or type(deps.MarketCallPlan.describe) ~= "function"
        or type(deps.NativeDispatchAdapter) ~= "table"
        or type(deps.NativeDispatchAdapter.new) ~= "function"
        or type(deps.NativeRemoteResolver) ~= "table"
        or type(deps.NativeRemoteResolver.new) ~= "function"
        or type(deps.RequestLane) ~= "table"
        or type(deps.RequestLane.new) ~= "function"
        or type(deps.ResourceReservations) ~= "table"
        or type(deps.ResourceReservations.new) ~= "function"
        or type(deps.PendingAction) ~= "table"
        or type(deps.PendingAction.Capture) ~= "function"
        or type(deps.NativeEventAdapter) ~= "table"
        or type(deps.NativeEventAdapter.fromFolder) ~= "function"
        or type(deps.ExecutorRuntimeAdapter) ~= "table"
        or type(deps.ExecutorRuntimeAdapter.new) ~= "function"
        or (not currentClient and type(deps.executorRuntimeApi) ~= "table")
        or (not currentClient and deps.remotesFolder == nil)
        or type(deps.ExecutorStorageAdapter) ~= "table"
        or type(deps.ExecutorStorageAdapter.new) ~= "function"
        or (not currentClient and type(deps.executorStorageApi) ~= "table")
        or (not currentClient and type(deps.nativeState) ~= "table")
        or type(deps.identity) ~= "table"
        or (not currentClient and type(deps.clock) ~= "table")
        or type(deps.CompatibilityGate) ~= "table"
        or type(deps.CompatibilityGate.new) ~= "function"
        or (not currentClient and (type(deps.sourceObserver) ~= "table"
            or type(deps.sourceObserver.Read) ~= "function"))
        or (currentClient and (type(deps.NativeClientBindings) ~= "table"
            or type(deps.NativeClientBindings.read) ~= "function"
            or type(deps.NativeClientObserver) ~= "table"
            or type(deps.NativeClientObserver.new) ~= "function"
            or type(deps.NativeExecutorCapabilities) ~= "table"
            or type(deps.NativeExecutorCapabilities.new) ~= "function"
            or deps.clientGame == nil
            or type(deps.clientRequire) ~= "function"
            or type(deps.clientHash) ~= "function"
            or type(deps.executorEnv) ~= "table"
            or type(deps.scheduler) ~= "table"
            or deps.httpService == nil))
        or type(deps.expectedGameVersion) ~= "string"
        or type(deps.fingerprint) ~= "string" then
        return nil, "Missing explicit runtime host capabilities"
    end
    local remotesFolder = deps.remotesFolder
    local nativeState = deps.nativeState
    local sourceObserver = deps.sourceObserver
    local executorRuntimeApi = deps.executorRuntimeApi
    local executorStorageApi = deps.executorStorageApi
    local clock = deps.clock
    local currentShop = deps.currentShop
    local currentCrateLuck = deps.currentCrateLuck
    local currentGlobalBoss = deps.currentGlobalBoss
    local currentEventShop = deps.currentEventShop
    local currentTerritorySeason = deps.currentTerritorySeason
    local currentDailyBuffRules = deps.currentDailyBuffRules
    local groupLookup = deps.groupLookup
    local rewardsConfig = deps.config
    local clientBindings
    if currentClient then
        -- Restore a captured closed owner's exact wrappers before a fresh read
        -- can mistake them for the native functions. Active/unknown owners hold.
        if type(deps.NativeCombatLease) == "table" then
            if type(deps.NativeCombatLease.cleanup) ~= "function" then
                return nil, "Native Combat cleanup capability unavailable"
            end
            local cleaned, complete, cleanupReason = pcall(deps.NativeCombatLease.cleanup,
                deps.executionRegistry)
            if not cleaned or complete ~= true then
                return nil, "Native Combat cleanup unconfirmed: "
                    .. (cleaned and tostring(cleanupReason or "Previous owner still holds custody")
                        or "Previous owner cleanup raised")
            end
        end
        if type(deps.NativePrestigeLease) == "table" then
            if type(deps.NativePrestigeLease.cleanup) ~= "function" then
                return nil, "Native Prestige cleanup capability unavailable"
            end
            local cleaned, complete, cleanupReason = pcall(deps.NativePrestigeLease.cleanup, deps.executionRegistry)
            if not cleaned or complete ~= true then
                return nil, "Native Prestige cleanup unconfirmed: "
                    .. (cleaned and tostring(cleanupReason or "Previous owner still holds custody") or "Previous owner cleanup raised")
            end
        end
        local bound, bindings = pcall(deps.NativeClientBindings.read,
            deps.clientGame, deps.clientRequire, deps.executorEnv and deps.executorEnv.getupvalues)
        if not bound or type(bindings) ~= "table"
            or bindings.remotesFolder == nil
            or type(bindings.nativeState) ~= "table"
            or type(bindings.gameData) ~= "table"
            or type(bindings.config) ~= "table"
            or type(bindings.gearSets) ~= "table"
            or type(bindings.combatRules) ~= "table" then
            return nil, "Current client bindings unavailable"
        end
        clientBindings = bindings
        local observed, observer = pcall(deps.NativeClientObserver.new,
            deps.clientGame, deps.clientRequire, deps.clientHash)
        if not observed or type(observer) ~= "table"
            or type(observer.Read) ~= "function" then
            return nil, "Current client observer unavailable"
        end
        remotesFolder = bindings.remotesFolder
        nativeState = bindings.nativeState
        sourceObserver = observer
        currentShop = bindings.currentShop
        currentCrateLuck = bindings.currentCrateLuck
        currentGlobalBoss = bindings.currentGlobalBoss
        currentEventShop = bindings.currentEventShop
        currentTerritorySeason = bindings.currentTerritorySeason
        currentDailyBuffRules = bindings.currentDailyBuffRules
        groupLookup = bindings.groupLookup
        rewardsConfig = bindings.config
        local adapted, capabilities = pcall(
            deps.NativeExecutorCapabilities.new,
            deps.executorEnv, deps.scheduler, deps.httpService)
        if not adapted or type(capabilities) ~= "table"
            or type(capabilities.executorRuntimeApi) ~= "table"
            or type(capabilities.executorStorageApi) ~= "table"
            or type(capabilities.clock) ~= "table"
            or type(capabilities.clock.Now) ~= "function" then
            return nil, "Current executor capabilities unavailable"
        end
        executorRuntimeApi = capabilities.executorRuntimeApi
        executorStorageApi = capabilities.executorStorageApi
        clock = capabilities.clock
    end
    local gateOk, compatibility = pcall(
        deps.CompatibilityGate.new, {
            place = deps.identity.place,
            account = deps.identity.account,
            gameVersion = deps.expectedGameVersion,
            fingerprint = deps.fingerprint,
        }, sourceObserver)
    if not gateOk or type(compatibility) ~= "table" then
        return nil, "Current client compatibility unavailable"
    end
    local compatible, accepted, gateReason = pcall(compatibility.Verify,
        compatibility)
    if not compatible or accepted ~= true then
        return nil, "Current client compatibility not verified: "
            .. (compatible and tostring(gateReason or "Unspecified mismatch")
                or "Verification raised")
    end
    local host
    local appDeps = {}
    for key, value in pairs(deps) do appDeps[key] = value end
    appDeps.remotesFolder = remotesFolder
    appDeps.nativeState = nativeState
    appDeps.sourceObserver = sourceObserver
    appDeps.executorRuntimeApi = executorRuntimeApi
    appDeps.executorStorageApi = executorStorageApi
    appDeps.clock = clock
    if clientBindings then
        appDeps.gameData = clientBindings.gameData
        appDeps.marketPresence = clientBindings.marketPresence
        appDeps.config = clientBindings.config
        appDeps.gearSets = clientBindings.gearSets
        appDeps.combatRules = clientBindings.combatRules
        appDeps.bossStages = clientBindings.bossStages
    end
    local laneCreated, requestLane = pcall(deps.RequestLane.new, clock)
    if not laneCreated or type(requestLane) ~= "table" then return nil, "Shared request lane unavailable" end
    local nativeRemoteLink
    if currentClient then nativeRemoteLink = clientBindings.nativeRemoteLink
    else nativeRemoteLink = deps.nativeRemoteLink end
    local resolved, resolver = pcall(
        deps.NativeRemoteResolver.new, remotesFolder, requestLane, nativeRemoteLink)
    if not resolved or type(resolver) ~= "table"
        or type(resolver.Invoke) ~= "function"
        or type(resolver.Close) ~= "function" then
        return nil, "Current Remotes folder unavailable"
    end
    appDeps.requestLane = requestLane
    local eventsOk, events = pcall(deps.NativeEventAdapter.fromFolder,
        remotesFolder, nativeState)
    if not eventsOk or type(events) ~= "table" then
        resolver:Close()
        return nil, "Current Sync or State feed unavailable"
    end
    local runtimeApi = {}
    for key, value in pairs(executorRuntimeApi) do
        if key ~= "invoke" and key ~= "invokeOwned" then runtimeApi[key] = value end
    end
    runtimeApi.invoke = function(remote, ...)
        local checked, current = pcall(compatibility.Verify,
            compatibility)
        if not checked or current ~= true then
            if host then host:Destroy() else resolver:Close() end
            error("Current client compatibility not verified")
        end
        return resolver:Invoke(remote, ...)
    end
    runtimeApi.invokeOwned = function(token, remote, ...)
        local checked, current = pcall(compatibility.Verify, compatibility)
        if not checked or current ~= true then
            if host then host:Destroy() else resolver:Close() end
            error("Current client compatibility not verified")
        end
        return resolver:InvokeOwned(token, remote, ...)
    end
    local runtimeOk, runtimeCaps = pcall(
        deps.ExecutorRuntimeAdapter.new,
        runtimeApi)
    if not runtimeOk or type(runtimeCaps) ~= "table"
        or type(runtimeCaps.nativeExecutor) ~= "table" then
        resolver:Close()
        return nil, "Executor runtime startup failed"
    end
    runtimeCaps.nativeExecutor.InFlight = function()
        return resolver:InFlight()
    end
    local storageOk, storage = pcall(
        deps.ExecutorStorageAdapter.new,
        executorStorageApi)
    if not storageOk or type(storage) ~= "table" then
        resolver:Close()
        return nil, "Executor storage startup failed"
    end
    appDeps.files = storage.files
    appDeps.codec = storage.codec
    appDeps.sha256 = storage.sha256
    appDeps.nativeRecallLease, appDeps.nativeRecallRuntime = nil, nil
    if currentClient and type(deps.NativeRecallLease) == "table" and type(deps.NativeRecallLease.bind) == "function" then
        local bound, lease = pcall(deps.NativeRecallLease.bind, {game = deps.clientGame, env = deps.executorEnv,
            registry = deps.executionRegistry, requireModule = deps.clientRequire, clock = clock, account = deps.identity.account})
        if bound and type(lease) == "table" then appDeps.nativeRecallLease = lease end
    elseif not currentClient then
        appDeps.nativeRecallLease, appDeps.nativeRecallRuntime = deps.nativeRecallLease, deps.nativeRecallRuntime
    end
    local callPlan = deps.NativeCallPlan.withMarket(
        deps.NativeCallPlan.withCombat(
            deps.NativeCallPlan.withCollection(
                deps.NativeCallPlan.withInventory(
                    deps.NativeCallPlan.withCrew(deps.CrewCallPlan, deps.CrewReplacement),
                    deps.InventoryCallPlan), deps.CollectionCallPlan),
            deps.CombatCallPlan), deps.MarketCallPlan)
    if type(deps.FamilyCallPlan) == "table" then
        callPlan = deps.NativeCallPlan.withFamily(callPlan, deps.FamilyCallPlan)
    end
    if type(deps.TerritoryCallPlan) == "table" then
        local territoryPlan = deps.TerritoryCallPlan
        if appDeps.nativeRecallLease or appDeps.nativeRecallRuntime then
            -- App creates the guarded store before the Territory owner. Describe
            -- only after that owner exists; startup cannot allocate or send.
            local original, cachedOwner, cachedPlan = territoryPlan, nil, nil
            territoryPlan = {describe = function(proposal)
                local owner = appDeps.nativeRecallRuntime
                if owner and type(original.withRecall) == "function" then
                    if cachedOwner ~= owner then cachedOwner, cachedPlan = owner, original.withRecall(original, owner) end
                    return cachedPlan.describe(proposal)
                end
                return original.describe(proposal)
            end}
        end
        callPlan = deps.NativeCallPlan.withTerritory(callPlan, territoryPlan)
    end
    if type(deps.PrestigeReset) == "table" then
        callPlan = deps.NativeCallPlan.withPrestige(callPlan, deps.PrestigeReset)
    end
    if type(deps.EventShopBuyer) == "table" then
        callPlan = deps.NativeCallPlan.withEvents(callPlan, deps.EventShopBuyer)
    end
    appDeps.territoryCitySource = currentClient and clientBindings.currentTerritoryCities
        or not currentClient and deps.territoryCitySource or nil
    appDeps.playerInfoSource = currentClient and clientBindings.currentPlayerInfo or not currentClient and deps.playerInfoSource or nil
    appDeps.nativePrestigeController = currentClient and clientBindings.currentPrestigeController
        or not currentClient and deps.nativePrestigeController or nil
    appDeps.fightReceipts = nil
    local notifications = currentClient and clientBindings and clientBindings.currentFightNotifications
        or not currentClient and deps.nativeFightNotifications
    local resolverCurrent = resolver.Current
    local notificationCurrent = type(notifications) == "table" and notifications.Current
    appDeps.nativeReadSource = {Current = function(_, name)
        if type(resolverCurrent) ~= "function" or resolver.Current ~= resolverCurrent then return false end
        if currentClient or notifications then
            if type(notificationCurrent) ~= "function" or notifications.Current ~= notificationCurrent then return false end
            local ok, current = pcall(notificationCurrent, notifications)
            if not ok or current ~= true then return false end
        end
        local ok, current = pcall(resolverCurrent, resolver, name)
        return ok and current == true
    end}
    local nativeFrame = type(notifications) == "table" and notifications.CombatFrame
    appDeps.nativeReadSource.CombatFrame = function(_, native, targets)
        if type(nativeFrame) ~= "function" or notifications.CombatFrame ~= nativeFrame
            or not appDeps.nativeReadSource:Current("GetHitList") then return nil end
        local ok, value = pcall(nativeFrame, notifications, native, targets)
        if not ok or type(value) ~= "table" or not appDeps.nativeReadSource:Current("GetHitList")
            or notifications.CombatFrame ~= nativeFrame then return nil end
        return value
    end
    local nativeFriendship = type(notifications) == "table" and notifications.Friendship
    appDeps.nativeReadSource.Friendship = function(_, target)
        if type(nativeFriendship) ~= "function" or notifications.Friendship ~= nativeFriendship
            or not appDeps.nativeReadSource:Current("PlayerProfile") then return nil end
        local ok, value = pcall(nativeFriendship, notifications, target)
        if not ok or type(value) ~= "boolean" or not appDeps.nativeReadSource:Current("PlayerProfile")
            or notifications.Friendship ~= nativeFriendship then return nil end
        return value
    end
    if type(notifications) == "table" and type(deps.FightReceipts) == "table"
        and type(deps.FightReceipts.new) == "function" then
        local ok, owner = pcall(deps.FightReceipts.new, deps.identity, clock, requestLane, notifications, deps.fingerprint)
        if ok and type(owner) == "table" and type(owner.Close) == "function" then appDeps.fightReceipts = owner end
    end
    appDeps.heistProtocol = nil
    if currentClient and type(deps.NativeHeistLease) == "table" and type(deps.NativeHeistLease.bind) == "function"
        and type(deps.HeistProtocol) == "table" and type(deps.HeistProtocol.new) == "function" then
        local bound, lease = pcall(deps.NativeHeistLease.bind, {game = deps.clientGame, requireModule = deps.clientRequire,
            env = deps.executorEnv, registry = deps.executionRegistry, clock = clock, account = deps.identity.account,
            defer = function(fn) return deps.scheduler.defer(fn) end})
        if bound and type(lease) == "table" then
            local made, protocol = pcall(deps.HeistProtocol.new, {lease = lease, clock = clock,
                identity = deps.identity, hash = function(bytes) return deps.clientHash(bytes, "sha256"):lower() end,
                config = clientBindings.config})
            if made and type(protocol) == "table" then appDeps.heistProtocol = protocol else lease:Close() end
        end
    elseif not currentClient then appDeps.heistProtocol = deps.heistProtocol end
    appDeps.nativeCombatLease = nil
    if currentClient and type(deps.NativeCombatLease) == "table" and type(deps.NativeCombatLease.bind) == "function"
        and type(notifications) == "table" then
        local bound, owner = pcall(deps.NativeCombatLease.bind, {source = notifications, env = deps.executorEnv,
            clock = clock, identity = deps.identity, registry = deps.executionRegistry})
        if bound and type(owner) == "table" then appDeps.nativeCombatLease = owner end
    elseif not currentClient then appDeps.nativeCombatLease = deps.nativeCombatLease end
    appDeps.nativePrestigeLease = nil
    if currentClient and type(deps.NativePrestigeLease) == "table" and type(deps.NativePrestigeLease.bind) == "function" then
        local observedController = appDeps.nativePrestigeController
        appDeps.nativePrestigeController = nil
        local bound, owner = pcall(deps.NativePrestigeLease.bind, {game = deps.clientGame, requireModule = deps.clientRequire,
            env = deps.executorEnv, clock = clock, identity = deps.identity, registry = deps.executionRegistry})
        if bound and type(owner) == "table" and type(owner.Read) == "function" and type(owner.Current) == "function" then
            appDeps.nativePrestigeLease, appDeps.nativePrestigeController = owner, owner
        elseif bound and type(owner) == "table" and type(owner.Close) == "function" then owner:Close() end
        if type(observedController) == "table" and type(observedController.Close) == "function" then observedController:Close() end
    elseif not currentClient then appDeps.nativePrestigeLease = deps.nativePrestigeLease end
    local transportOk, transport = pcall(
        deps.NativeDispatchAdapter.new, callPlan,
        runtimeCaps.nativeExecutor, requestLane, clock, appDeps.fightReceipts, appDeps.heistProtocol, appDeps.nativeCombatLease, currentClient, appDeps.nativePrestigeLease, currentClient)
    if not transportOk or type(transport) ~= "table" then
        if appDeps.fightReceipts then appDeps.fightReceipts:Close() end
        if appDeps.heistProtocol then appDeps.heistProtocol:Close() end
        if appDeps.nativeCombatLease then appDeps.nativeCombatLease:Close() end
        if appDeps.nativePrestigeLease then appDeps.nativePrestigeLease:Close() end
        resolver:Close()
        return nil, "Native transport startup failed"
    end
    local deferredTransport
    if appDeps.nativeRecallLease or appDeps.nativeRecallRuntime then
        deferredTransport = {current = transport}
        local forward = {}
        for _, name in ipairs({"Validate", "Send", "InFlight", "ReadLease", "ReleaseResolved", "ReleaseExpired"}) do
            forward[name] = function(_, ...) return deferredTransport.current[name](deferredTransport.current, ...) end
        end
        setmetatable(forward, {__index = function(_, key) return deferredTransport.current[key] end})
        appDeps.transport = forward
    else appDeps.transport = transport end
    appDeps.shopQuoteSource = nil
    appDeps.rewardsSource = nil
    appDeps.crateLuckSource = nil
    appDeps.globalBossSource = nil
    appDeps.eventShopSource = nil
    appDeps.territorySeasonSource = nil
    if type(currentTerritorySeason) == "table" and type(deps.TerritorySeasonSource) == "table"
        and type(deps.TerritorySeasonSource.new) == "function" then
        local ok, source = pcall(deps.TerritorySeasonSource.new, currentTerritorySeason.readLive,
            currentTerritorySeason.status, deps.fingerprint, deps.release)
        if ok and type(source) == "table" and type(source.Enrich) == "function"
            and type(source.Close) == "function" and source.release == deps.release
            and source.sourceKey == deps.fingerprint:lower() then appDeps.territorySeasonSource = source end
    end
    if type(currentEventShop) == "table" and type(deps.NativeEventShopSource) == "table"
        and type(deps.NativeEventShopSource.new) == "function" then
        local ok, source = pcall(deps.NativeEventShopSource.new, currentEventShop.definition,
            currentEventShop.readAttributes, deps.fingerprint, deps.release)
        if ok and type(source) == "table" and type(source.Enrich) == "function"
            and type(source.Close) == "function" and source.release == deps.release
            and source.sourceKey == deps.fingerprint:lower() then appDeps.eventShopSource = source end
    end
    if type(currentGlobalBoss) == "table" and type(deps.NativeGlobalBossSource) == "table"
        and type(deps.NativeGlobalBossSource.new) == "function" and type(deps.GlobalBossState) == "table" then
        local ok, source = pcall(deps.NativeGlobalBossSource.new, currentGlobalBoss.rule,
            currentGlobalBoss.readAttributes, deps.GlobalBossState, currentGlobalBoss.userId,
            deps.fingerprint, deps.release)
        if ok and type(source) == "table" and type(source.Enrich) == "function"
            and type(source.Close) == "function" then appDeps.globalBossSource = source end
    end
    if currentClient
        and type(deps.NativeCrateLuckSource) == "table"
        and type(deps.NativeCrateLuckSource.new) == "function"
        and type(currentCrateLuck) == "table"
        and type(deps.release) == "string" then
        local ok, source = pcall(deps.NativeCrateLuckSource.new,
            currentCrateLuck, deps.release)
        if ok and type(source) == "table"
            and source.release == deps.release then
            appDeps.crateLuckSource = source
        end
    end
    if type(deps.NativeQuoteSource) == "table"
        and type(deps.NativeQuoteSource.new) == "function"
        and type(currentShop) == "table"
        and type(deps.release) == "string" then
        local ok, source = pcall(deps.NativeQuoteSource.new,
            currentShop, deps.release, deps.fingerprint)
        if ok and type(source) == "table"
            and source.release == deps.release
            and source.catalogKey == deps.fingerprint:lower() then
            appDeps.shopQuoteSource = source
        end
    end
    local groupId = type(rewardsConfig) == "table"
        and type(rewardsConfig.GROUP) == "table"
        and rewardsConfig.GROUP.id
    if type(deps.NativeRewardsSource) == "table"
        and type(deps.NativeRewardsSource.new) == "function"
        and type(currentDailyBuffRules) == "table"
        and type(groupLookup) == "function"
        and type(deps.release) == "string"
        and type(groupId) == "number" then
        local ok, source = pcall(deps.NativeRewardsSource.new,
            currentDailyBuffRules, groupLookup,
            clock, deps.release, deps.identity.account,
            groupId)
        if ok and type(source) == "table"
            and source.release == deps.release
            and source.account == deps.identity.account
            and source.groupId == groupId then
            appDeps.rewardsSource = source
        end
    end
    local function closeSources()
        for _, key in ipairs({ "shopQuoteSource", "globalBossSource", "eventShopSource", "territorySeasonSource",
            "rewardsSource", "fightReceipts", "nativePrestigeController", "heistProtocol", "nativeRecallRuntime", "nativeRecallLease", "nativeCombatLease" }) do
            local source = appDeps[key]
            if type(source) == "table"
                and type(source.Close) == "function" then
                pcall(source.Close, source)
            end
        end
    end
    local created, reader = pcall(deps.NativeSnapshotReader.new, deps.identity, clock, deps.fingerprint)
    if not created or type(reader) ~= "table" then
        closeSources()
        resolver:Close()
        requestLane:Close()
        return nil, "Native reader startup failed"
    end
    appDeps.nativeReader, appDeps.nativeExecutor = reader, runtimeCaps.nativeExecutor
    appDeps.onAppClosed = function()
        if host then host:Destroy() end
    end
    local made, app = pcall(deps.App.start, appDeps)
    if not made or type(app) ~= "table"
        or app.alive ~= true
        or type(app.Destroy) ~= "function"
        or type(app.Step) ~= "function" then
        local failure = "App startup returned invalid handle"
        if not made then
            local firstLine = tostring(app):match("^[^\r\n]+")
                or "Unknown construction error"
            failure = "App construction raised: "
                .. firstLine:sub(1, 88)
        end
        if made and type(app) == "table"
            and type(app.Destroy) == "function" then
            pcall(app.Destroy, app)
        end
        closeSources()
        resolver:Close()
        reader:Close()
        requestLane:Close()
        return nil, failure
    end
    if deferredTransport and appDeps.nativeRecallRuntime then
        local wrapped, sender = pcall(appDeps.nativeRecallRuntime.WrapTransport, appDeps.nativeRecallRuntime, transport)
        if not wrapped or type(sender) ~= "table" then
            closeSources(); resolver:Close(); reader:Close(); app:Destroy(); requestLane:Close()
            return nil, "Native Recall transport startup failed"
        end
        deferredTransport.current = sender
    end
    local driverOk, driver = pcall(deps.RuntimeDriver.new,
        app, reader)
    if not driverOk or type(driver) ~= "table" then
        closeSources()
        resolver:Close()
        pcall(reader.Close, reader)
        pcall(app.Destroy, app)
        return nil, "Runtime driver startup failed"
    end
    local loopOk, loop = pcall(deps.RuntimeLoop.new,
        driver, runtimeCaps.timer, 0.25)
    if not loopOk or type(loop) ~= "table" then
        closeSources()
        resolver:Close()
        pcall(driver.Close, driver)
        return nil, "Runtime loop startup failed"
    end
    local handles = {}
    host = { app = app, driver = driver, loop = loop,
        requestLane = requestLane,
        resolver = resolver,
        handles = handles, active = true }
    local refreshQueued = nil
    function host:RefreshGroupMembership()
        local source = appDeps.rewardsSource
        if not self.active or (refreshQueued and requestLane:Owns(refreshQueued))
            or type(source) ~= "table"
            or type(source.Refresh) ~= "function" then
            return false
        end
        local token = requestLane:TryAcquire("membership", "group:membership", clock:Now() + 5)
        if not token then return false end
        refreshQueued = token
        local scheduled, accepted = pcall(runtimeCaps.nativeExecutor.Schedule,
            runtimeCaps.nativeExecutor, function()
                if self.active and requestLane:Owns(token) then
                    pcall(source.Refresh, source,
                        deps.identity.account, groupId, function()
                            return self.active and requestLane:Owns(token)
                        end)
                end
                requestLane:Release(token, "membership_returned")
                if refreshQueued == token then refreshQueued = nil end
            end)
        if not scheduled or accepted == false then
            requestLane:Release(token, "membership_schedule_failed")
            if refreshQueued == token then refreshQueued = nil end
            return false
        end
        return true
    end
    function host:Destroy()
        if not self.active then return false end
        self.active = false
        disconnect(self.handles)
        -- Stop new loop work, then let App flush exact accepted receipts while
        -- their captured source and logical lease are still readable.
        local stopped, closed = pcall(self.loop.Close, self.loop)
        if not stopped or closed ~= true then pcall(self.driver.Close, self.driver) end
        requestLane:Close()
        closeSources()
        self.resolver:Close()
        return true
    end
    setmetatable(host, { __index = function(_, key)
        if key == "alive" then return app.alive end
        return nil
    end })
    for _, method in ipairs({ "CanReplace", "Set", "Pause", "Resume", "Stop",
        "Step", "Refresh", "ApplyProfile", "SaveProfile",
        "PreviewProfile", "SetAutoload", "SetNextLoad", "DeleteProfile", "SetProfileSync" }) do
        if type(app[method]) == "function" then
            host[method] = function(_, ...)
                return app[method](app, ...)
            end
        end
    end
    local function observe(method, payload, fullSync)
        if not host.active or app.alive == false then return end
        if fullSync then
            local checked, current = pcall(compatibility.Verify,
                compatibility)
            if not checked or current ~= true then
                host:Destroy()
                return
            end
            local source = appDeps.rewardsSource
            if type(source) == "table"
                and type(source.Membership) == "function" then
                local readOk, _, checkedAt = pcall(
                    source.Membership, source,
                    deps.identity.account, groupId)
                local clockOk, now = pcall(clock.Now,
                    clock)
                if not readOk or not clockOk
                    or type(now) ~= "number" or now ~= now
                    or type(checkedAt) ~= "number"
                    or checkedAt ~= checkedAt
                    or checkedAt > now or now - checkedAt > 20 then
                    host:RefreshGroupMembership()
                end
            end
        end
        local ok = pcall(method, driver, payload)
        if not ok then host:Destroy() end
    end
    local syncOk, sync = pcall(events.SubscribeSync,
        events, function(payload)
            observe(driver.ObserveSync, payload, true)
        end)
    if not syncOk or not disconnectable(sync) then
        host:Destroy()
        return nil, "Sync subscription failed"
    end
    handles[#handles + 1] = sync
    local changedOk, changed = pcall(events.SubscribeChanged,
        events, function(payload)
            observe(driver.ObserveChanged, payload, false)
        end)
    if not changedOk or not disconnectable(changed) then
        host:Destroy()
        return nil, "Changed-state subscription failed"
    end
    handles[#handles + 1] = changed

    if currentClient then
        local latestOk, latest = pcall(clientBindings.nativeState.latest)
        if not latestOk or type(latest) ~= "table" then
            host:Destroy()
            return nil, "Current client snapshot unavailable"
        end
        local seeded, syncAccepted = pcall(reader.ObserveSync, reader, latest)
        if not seeded or syncAccepted ~= true then
            host:Destroy()
            return nil, "Current client snapshot invalid"
        end
    end
    if not loop:Start() then
        host:Destroy()
        return nil, "Runtime timer failed"
    end
    return host, nil
end

return RuntimeHost
