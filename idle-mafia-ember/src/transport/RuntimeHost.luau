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
        or type(deps.NativeDispatchAdapter) ~= "table"
        or type(deps.NativeDispatchAdapter.new) ~= "function"
        or type(deps.NativeRemoteResolver) ~= "table"
        or type(deps.NativeRemoteResolver.new) ~= "function"
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
    local currentDailyBuffRules = deps.currentDailyBuffRules
    local groupLookup = deps.groupLookup
    local rewardsConfig = deps.config
    local clientBindings
    if currentClient then
        local bound, bindings = pcall(deps.NativeClientBindings.read,
            deps.clientGame, deps.clientRequire)
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
    local compatible, accepted = pcall(compatibility.Verify,
        compatibility)
    if not compatible or accepted ~= true then
        return nil, "Current client compatibility not verified"
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
        appDeps.config = clientBindings.config
        appDeps.gearSets = clientBindings.gearSets
        appDeps.combatRules = clientBindings.combatRules
    end
    local resolved, resolver = pcall(
        deps.NativeRemoteResolver.new, remotesFolder)
    if not resolved or type(resolver) ~= "table"
        or type(resolver.Invoke) ~= "function"
        or type(resolver.Close) ~= "function" then
        return nil, "Current Remotes folder unavailable"
    end
    local eventsOk, events = pcall(deps.NativeEventAdapter.fromFolder,
        remotesFolder, nativeState)
    if not eventsOk or type(events) ~= "table" then
        resolver:Close()
        return nil, "Current Sync or State feed unavailable"
    end
    local runtimeApi = {}
    for key, value in pairs(executorRuntimeApi) do
        if key ~= "invoke" then runtimeApi[key] = value end
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
    local runtimeOk, runtimeCaps = pcall(
        deps.ExecutorRuntimeAdapter.new,
        runtimeApi)
    if not runtimeOk or type(runtimeCaps) ~= "table" then
        resolver:Close()
        return nil, "Executor runtime startup failed"
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
    local transportOk, transport = pcall(
        deps.NativeDispatchAdapter.new, deps.NativeCallPlan,
        runtimeCaps.nativeExecutor)
    if not transportOk or type(transport) ~= "table" then
        resolver:Close()
        return nil, "Native transport startup failed"
    end
    appDeps.transport = transport
    appDeps.shopQuoteSource = nil
    appDeps.rewardsSource = nil
    if type(deps.NativeQuoteSource) == "table"
        and type(deps.NativeQuoteSource.new) == "function"
        and type(deps.currentShop) == "table"
        and type(deps.release) == "string" then
        local ok, source = pcall(deps.NativeQuoteSource.new,
            deps.currentShop, deps.release, deps.fingerprint)
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
        for _, key in ipairs({ "shopQuoteSource",
            "rewardsSource" }) do
            local source = appDeps[key]
            if type(source) == "table"
                and type(source.Close) == "function" then
                pcall(source.Close, source)
            end
        end
    end
    appDeps.onAppClosed = function()
        if host then host:Destroy() end
    end
    local made, app = pcall(deps.App.start, appDeps)
    if not made or type(app) ~= "table"
        or app.alive ~= true
        or type(app.Destroy) ~= "function"
        or type(app.Step) ~= "function" then
        if made and type(app) == "table"
            and type(app.Destroy) == "function" then
            pcall(app.Destroy, app)
        end
        closeSources()
        resolver:Close()
        return nil, "App startup failed"
    end
    local created, reader = pcall(deps.NativeSnapshotReader.new,
        deps.identity, clock)
    if not created or type(reader) ~= "table" then
        closeSources()
        resolver:Close()
        pcall(app.Destroy, app)
        return nil, "Native reader startup failed"
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
        resolver = resolver,
        handles = handles, active = true }
    local refreshQueued = false
    function host:RefreshGroupMembership()
        local source = appDeps.rewardsSource
        if not self.active or refreshQueued
            or type(source) ~= "table"
            or type(source.Refresh) ~= "function" then
            return false
        end
        refreshQueued = true
        local scheduled, accepted = pcall(runtimeCaps.nativeExecutor.Schedule,
            runtimeCaps.nativeExecutor, function()
                if self.active then
                    pcall(source.Refresh, source,
                        deps.identity.account, groupId)
                end
                refreshQueued = false
            end)
        if not scheduled or accepted == false then
            refreshQueued = false
            return false
        end
        return true
    end
    function host:Destroy()
        if not self.active then return false end
        self.active = false
        closeSources()
        self.resolver:Close()
        disconnect(self.handles)
        if not self.loop:Close() then self.driver:Close() end
        return true
    end
    setmetatable(host, { __index = function(_, key)
        if key == "alive" then return app.alive end
        return nil
    end })
    for _, method in ipairs({ "Set", "Pause", "Resume", "Stop",
        "Step", "Refresh", "ApplyProfile", "SaveProfile",
        "PreviewProfile" }) do
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
        local seeded, accepted = pcall(reader.ObserveSync, reader, latest)
        if not seeded or accepted ~= true then
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
