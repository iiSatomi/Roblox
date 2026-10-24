-- Inert composition. No game services, remote calls, timers or account files.
local App = {}

local function runtimeInstance(value)
    return type(value) == "table"
        and type(value.Status) == "function"
        and type(value.Step) == "function"
        and type(value.Pause) == "function"
        and type(value.Resume) == "function"
        and type(value.Stop) == "function"
        and type(value.Close) == "function"
        and value or nil
end

function App.start(dependencies)
    assert(dependencies.automationRuntimeInstance == nil
        or runtimeInstance(dependencies.automationRuntimeInstance),
        "Invalid automation runtime instance")
    assert(dependencies.jobsRuntimeInstance == nil
        or runtimeInstance(dependencies.jobsRuntimeInstance),
        "Invalid Jobs runtime instance")
    if dependencies.activateStorage == true then
        assert(type(dependencies.StorageAssembly) == "table"
            and type(dependencies.StorageAssembly.new) == "function"
            and type(dependencies.ProfileStore) == "table"
            and type(dependencies.ProfileStore.new) == "function",
            "Invalid storage activation")
        local stores, reason = dependencies.StorageAssembly.new(dependencies)
        assert(stores and type(stores.ProfileStorage) == "table"
            and type(stores.storage) == "table",
            reason or "Storage assembly failed")
        dependencies.ProfileStorage = stores.ProfileStorage
        dependencies.storage = stores.storage
    end
    local automation = runtimeInstance(dependencies.automationRuntimeInstance)
        or runtimeInstance(dependencies.AutomationRuntime)
    local jobs = runtimeInstance(dependencies.jobsRuntimeInstance)
        or runtimeInstance(dependencies.JobsRuntime)
    if dependencies.activateAutomation == true then
        assert(not automation and not jobs
            and type(dependencies.RuntimeAssembly) == "table"
            and type(dependencies.RuntimeAssembly.start) == "function",
            "Invalid runtime activation")
        local reason
        automation, reason = dependencies.RuntimeAssembly.start(dependencies)
        assert(automation, reason or "Runtime assembly failed")
    end
    assert(not (automation and jobs),
        "Use one automation runtime")
    local runtime = automation or jobs
    local self = { alive = true, model = dependencies.Settings.new(dependencies.Catalog),
        ui = nil, staged = nil, jobsRuntime = jobs,
        automationRuntime = automation }
    if dependencies.ProfileStorage then
        assert(type(dependencies.ProfileStore) == "table"
            and type(dependencies.ProfileStore.new) == "function"
            and type(dependencies.identity) == "table",
            "Profile storage needs an account identity and adapter")
        self.profileStore = dependencies.ProfileStore.new(
            dependencies.ProfileStorage, self.model,
            dependencies.identity.account, dependencies.identity.place)
    end

    local function closed()
        if not self.alive then return end
        self.alive = false
        self.model:Stop()
        if runtime then runtime:Close() end
        if type(dependencies.onAppClosed) == "function" then
            pcall(dependencies.onAppClosed)
        end
    end

    local function render(view, command)
        return pcall(function()
            local projected = { values = view.values, paused = view.paused,
                stopped = view.stopped,
                jobsRuntime = self.jobsRuntime and self.jobsRuntime:Status() or nil,
                automationRuntime = self.automationRuntime
                    and self.automationRuntime:Status() or nil }
            local accepted, reason = self.ui:Render(projected)
            if accepted and command then self.ui:RecordActivity(command) end
            return accepted, reason
        end)
    end

    function self:Refresh(command)
        if not self.alive then return false, "Prototype is closed" end
        local ok, accepted, reason = render(self.model, command)
        if not ok or accepted == false then
            self.model:Pause()
            if runtime then runtime:Pause() end
            self.ui.lastError = tostring(reason or accepted)
            if not ok then self.ui:Fail(self.ui.lastError) end
            return false, self.ui.lastError
        end
        return true, nil
    end

    local function applyPrepared(values, pause, command)
        local view = { values = values, stopped = self.model.stopped,
            paused = pause or self.model.paused }
        -- Finish every fallible UI update before committing preferences.
        local ok, accepted, reason = render(view, command)
        if not ok or accepted == false then
            local failure = tostring(reason or accepted)
            local restored, result = pcall(self.ui.ApplyValues, self.ui, self.model.values)
            if not ok or not restored or result == false or self.ui.degraded then
                self.model:Pause()
                if runtime then runtime:Pause() end
                self.ui:Fail(failure)
            end
            return false, failure
        end
        self.model:Commit(values, pause)
        if pause and runtime then runtime:Pause() end
        return true, nil
    end

    function self:ApplyProfile(profile)
        if not self.alive then return false, "Prototype is closed" end
        local prepared, reason = self.model:Validate(profile)
        if not prepared then return false, reason end
        return applyPrepared(prepared, true, "Applied choices; session paused")
    end

    function self:SaveProfile(name)
        if not self.alive or not self.profileStore then
            return false, "Profile storage unavailable"
        end
        local saved, reason = self.profileStore:Save(
            name, self.model:Snapshot())
        if saved then self.ui.profileStatus:Set("Saved locally: " .. name, true) end
        return saved, reason
    end

    function self:PreviewProfile(name)
        if not self.alive or not self.profileStore then
            return false, "Profile storage unavailable"
        end
        local profile, reason = self.profileStore:Load(name)
        if not profile then return false, reason end
        self.staged = profile
        self.ui.profileStatus:Set("Ready to apply: " .. name, true)
        return true, nil
    end

    function self:Set(key, value)
        if not self.alive then return false, "Prototype is closed" end
        if not self.model.specs[key] or value == nil then return false, "Invalid preference: " .. tostring(key) end
        local prepared, reason = self.model:Validate({ schema = 1, values = { [key] = value } })
        if not prepared then return false, reason end
        return applyPrepared(prepared, false, "Changed " .. key)
    end

    function self:Pause()
        if not self.alive then return false, "Prototype is closed" end
        self.model:Pause()
        if runtime then runtime:Pause() end
        return self:Refresh("Paused")
    end
    function self:Resume()
        if not self.alive then return false, "Prototype is closed" end
        if runtime and runtime:Status().state == "stopped" then
            return false, "Automation stopped; reload required"
        end
        self.model:Resume()
        local ok, reason = self:Refresh(runtime and "Resumed automation" or "Resumed UI only")
        if ok and runtime then runtime:Resume() end
        return ok, reason
    end
    function self:Stop()
        if not self.alive then return false, "Prototype is closed" end
        self.model:Stop()
        if runtime then runtime:Stop() end
        return self:Refresh("Stopped; choices cleared")
    end
    function self:Step(raw)
        if not self.alive then return false, "Prototype is closed" end
        if not runtime then return false, "Automation runtime unavailable" end
        local ready, reason = self:Refresh()
        if not ready then return false, reason end
        local enabled = not self.model.paused and not self.model.stopped
        local settings
        if self.automationRuntime then
            settings = {
                jobs = { enabled = enabled and self.model.values["jobs.enabled"] == true,
                    policy = self.model.values["jobs.policy"],
                    selectedJobId = self.model.values["jobs.custom.selectedJobId"] },
                operations = { enabled = enabled
                    and self.model.values["operations.enabled"] == true,
                    policy = self.model.values["operations.policy"] },
                collect = { enabled = enabled
                    and self.model.values["collect.enabled"] == true },
                skills = { enabled = enabled
                    and self.model.values["skills.enabled"] == true,
                    stat = self.model.values["skills.custom.stat"],
                    maxAllocations = self.model.values["skills.custom.maxAllocations"],
                    batchSize = self.model.values["skills.custom.batchSize"] },
                groupBonus = { enabled = enabled
                    and self.model.values["groupBonus.enabled"] == true },
                monthlyRewards = { enabled = enabled
                    and self.model.values["monthlyRewards.enabled"] == true },
                trophies = { enabled = enabled
                    and self.model.values["trophies.enabled"] == true },
                playtime = { enabled = enabled
                    and self.model.values["playtime.enabled"] == true },
                contracts = { enabled = enabled
                    and self.model.values["contracts.enabled"] == true },
                bonuses = { enabled = enabled
                    and self.model.values["bonuses.enabled"] == true },
                briefcases = { enabled = enabled
                    and self.model.values["briefcases.enabled"] == true },
                bank = { enabled = enabled
                    and self.model.values["bank.enabled"] == true,
                    depositThreshold = self.model.values["bank.custom.depositThreshold"],
                    cashToKeep = self.model.values["bank.custom.cashToKeep"] },
                safehouse = { enabled = enabled
                    and self.model.values["safehouse.enabled"] == true,
                    maxTier = self.model.values["safehouse.custom.maxTier"],
                    maxCost = self.model.values["safehouse.custom.maxCost"],
                    cashReserve = self.model.values["safehouse.custom.cashReserve"] },
                withdraw = { enabled = enabled
                    and self.model.values["withdraw.enabled"] == true,
                    maxWithdrawal = self.model.values["withdraw.custom.maxWithdrawal"],
                    allowOperations = enabled
                        and self.model.values["operations.enabled"] == true,
                    allowSafehouse = enabled
                        and self.model.values["safehouse.enabled"] == true },
            }
            -- New descriptor slices inherit their own switch, policy and
            -- bounded Custom values until they need special dependencies.
            for id in pairs(self.automationRuntime.features) do
                if settings[id] == nil then
                    local feature = { enabled = enabled
                        and self.model.values[id .. ".enabled"] == true }
                    local policy = self.model.values[id .. ".policy"]
                    if policy ~= nil then feature.policy = policy end
                    local prefix = id .. ".custom."
                    for key, value in pairs(self.model.values) do
                        if string.sub(key, 1, #prefix) == prefix then
                            feature[string.sub(key, #prefix + 1)] = value
                        end
                    end
                    settings[id] = feature
                end
            end
        else
            settings = { enabled = enabled
                and self.model.values["jobs.enabled"] == true,
                policy = self.model.values["jobs.policy"],
                selectedJobId = self.model.values["jobs.custom.selectedJobId"] }
        end
        local ok, result = pcall(runtime.Step, runtime, raw, settings)
        if not ok then
            self.model:Pause()
            runtime:Pause()
            self.ui:Fail(tostring(result))
            return false, tostring(result)
        end
        return self:Refresh()
    end
    function self:Destroy()
        if not self.alive then return false end
        closed() -- Fence queued callbacks before Ember begins close/revert.
        self.ui:Destroy()
        return true
    end

    local function change(key, value, handle)
        if not self.alive or not self.ui or not handle then return end
        local ok, current = pcall(handle.Get, handle)
        if not ok or current ~= value then return end -- Ignore superseded async callbacks.
        if self.ui.numeric[key] then value = tonumber(value) end
        local accepted, reason = self:Set(key, value)
        if not accepted then
            self.ui.lastError = reason
            self:Refresh("Rejected invalid preference")
        end
    end
    local function command(name)
        if not self.alive or not self.ui then return end
        if name == "pause" then self:Pause()
        elseif name == "resume" then self:Resume()
        elseif name == "stop" then self:Stop()
        elseif name == "unload" then self:Destroy()
        elseif name == "stage" then
            self.staged = self.model:Snapshot()
            self.ui.profileStatus:Set("Staged locally", true)
        elseif name == "discard" then
            self.staged = nil
            self.ui.profileStatus:Set("None", true)
        elseif name == "apply" then
            local ok, reason = self:ApplyProfile(self.staged)
            if not ok then self.ui.lastError = reason; self:Refresh("Profile not applied") end
        elseif name == "saveProfile" or name == "previewProfile" then
            if not self.ui.profileName then return end
            local read, profileName = pcall(self.ui.profileName.Get,
                self.ui.profileName)
            local ok, reason
            if not read then
                ok, reason = false, "Profile name unavailable"
            elseif name == "saveProfile" then
                ok, reason = self:SaveProfile(profileName)
            else
                ok, reason = self:PreviewProfile(profileName)
            end
            if not ok then self.ui.lastError = reason
                self:Refresh("Profile operation rejected") end
        end
    end

    local created, uiOrReason = pcall(dependencies.EmberAdapter.new,
        dependencies.Ember, dependencies.Catalog, {
        change = change, command = command, destroy = closed,
        profileStorage = self.profileStore ~= nil,
        overviewModule = dependencies.OverviewTab,
        heistsModule = dependencies.HeistsTab,
        jobsModule = dependencies.JobsTab,
        operationsModule = dependencies.OperationsTab,
        favorsModule = dependencies.FavorsTab,
        combatModule = dependencies.CombatTab,
        crewModule = dependencies.CrewTab,
        inventoryModule = dependencies.InventoryTab,
            collectionModule = dependencies.CollectionTab,
            moneyModule = dependencies.MoneyTab,
            propertyModule = dependencies.PropertyTab,
            safehouseModule = dependencies.SafehouseTab,
            prestigeModule = dependencies.PrestigeTab,
            shopModule = dependencies.ShopTab,
            blackMarketModule = dependencies.BlackMarketTab,
            familyModule = dependencies.FamilyTab,
            territoryModule = dependencies.TerritoryTab,
            contractsModule = dependencies.ContractsTab,
            trophiesModule = dependencies.TrophiesTab,
            skillsModule = dependencies.SkillsTab,
            rewardsModule = dependencies.RewardsTab,
            eventsModule = dependencies.EventsTab,
            profilesModule = dependencies.ProfilesTab,
            settingsModule = dependencies.SettingsTab,
            activityModule = dependencies.ActivityTab,
    })
    if not created then closed(); error(uiOrReason, 0) end
    self.ui = uiOrReason
    local ok, reason = self:Refresh("Created inert UI")
    if not ok then self:Destroy(); error(reason, 0) end
    return self
end

return App
