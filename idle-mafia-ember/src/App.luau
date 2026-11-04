-- Inert composition. Account metadata reads require an explicit review command.
local App = {}
local energyActivities = { jobs = true, heists = true, favors = true, sabotage = true }

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
    local allowedFeatures = runtime and dependencies.allowedFeatures or nil
    local function allowed(values)
        if type(allowedFeatures) ~= "table" then return true end
        for key, value in pairs(values) do
            if value == true and type(key) == "string"
                and key:sub(-8) == ".enabled"
                and allowedFeatures[key:sub(1, -9)] ~= true then
                return false
            end
        end
        return true
    end
    local self = { alive = true,
        model = dependencies.Settings.new(dependencies.Catalog, runtime ~= nil),
        ui = nil, staged = nil, profileSync = false, profileModified = false,
        profileSaving = false, savedStateReview = nil, savedStatePage = 1, reviewBusy = false,
        jobsRuntime = jobs,
        automationRuntime = automation }
    local savedStateReader, savedStateUnavailable
    if type(dependencies.SavedStateReview) == "table" and type(dependencies.SavedStateReview.new) == "function" then
        local ok, reader, reason = pcall(dependencies.SavedStateReview.new, dependencies)
        if ok then savedStateReader, savedStateUnavailable = reader, reason
        else savedStateUnavailable = "Read-only review unavailable; history unknown" end
    else savedStateUnavailable = "Read-only review unavailable; history unknown" end
    function self:ReviewSavedState()
        if not self.alive or self.reviewBusy then return false end
        if not savedStateReader then return false, savedStateUnavailable end
        self.reviewBusy = true
        local ok, report = pcall(savedStateReader.Read, savedStateReader, function() return self.alive end)
        self.reviewBusy = false
        if not self.alive then return false end
        self.savedStateReview = ok and report or {notice="Review only; does not authorize activation or clear unknown history.",
            status="Unknown: read-only review failed", rows={}, completeHistory=false, authorizesActivation=false}
        self.savedStatePage = 1
        self:Refresh("Reviewed saved-state metadata only")
        return ok
    end
    if runtime and type(runtime.SetSelectionGuard) == "function" then
        runtime:SetSelectionGuard(function(feature)
            if not self.alive or self.model.paused or self.model.stopped
                or self.model.values[feature .. ".enabled"] ~= true
                or (type(allowedFeatures) == "table" and allowedFeatures[feature] ~= true) then return nil end
            local choices, prefix = {}, feature .. "."
            for key, value in pairs(self.model.values) do
                if key:sub(1, #prefix) == prefix then choices[key] = value end
            end
            if feature == "withdraw" then
                -- A queued shortfall belongs to the original purchase choices.
                for _, purpose in ipairs({ "heists", "properties", "operations", "safehouse", "shop" }) do
                    local origin = purpose .. "."
                    for key, value in pairs(self.model.values) do
                        if key:sub(1, #origin) == origin then choices[key] = value end
                    end
                end
                choices["shared.energyReserve"] = self.model.values["shared.energyReserve"]
            end
            if energyActivities[feature] and self.model.specs["shared.energyReserve"] then
                choices["shared.energyReserve"] = self.model.values["shared.energyReserve"]
            end
            if feature == "combat" or feature == "warCombat" or feature == "sabotage" then
                for _, name in ipairs({"allies", "enemies", "mode"}) do
                    choices["alliance." .. name] = self.model.values["alliance." .. name]
                end
            end
            return choices
        end)
    end
    if dependencies.ProfileStorage then
        assert(type(dependencies.ProfileStore) == "table"
            and type(dependencies.ProfileStore.new) == "function"
            and type(dependencies.identity) == "table",
            "Profile storage needs an account identity and adapter")
        self.profileStore = dependencies.ProfileStore.new(
            dependencies.ProfileStorage, self.model,
            dependencies.identity.account, dependencies.identity.place, dependencies.storage)
        self.profileSync, self.profileSyncError = self.profileStore:GetSync()
    end
    local startupNote = runtime and "Runtime attached; all features off"
        or "Created inert UI"
    if runtime and self.profileStore then
        local name, autoloadReason = self.profileStore:ConsumeNextLoad()
        local once = name ~= nil
        if not name and not autoloadReason then name, autoloadReason = self.profileStore:GetAutoload() end
        if autoloadReason then
            startupNote = autoloadReason .. "; all features off"
        elseif name then
            local profile, loadReason = self.profileStore:Load(name)
            local prepared, validationReason = nil, nil
            if profile then prepared, validationReason = self.model:Validate(profile, true) end
            if prepared and allowed(prepared) then
                self.model:Commit(prepared, false)
                self.currentProfile = name
                startupNote = (once and "Loaded next-launch profile: " or "Autoloaded profile: ") .. name
            else
                startupNote = (loadReason or validationReason
                    or "Autoload profile exceeds this runtime preview")
                    .. "; all features off"
            end
        end
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
                stopped = view.stopped, staged = self.staged,
                currentProfile = self.currentProfile, profileModified = self.profileModified,
                profileSync = self.profileSync, profileSyncError = self.profileSyncError,
                profileSaving = self.profileSaving, importReviewText = self.importReviewText,
                savedStateReview = self.savedStateReview, savedStatePage = self.savedStatePage or 1,
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
        if self.profileSaving then return false, "Profile save already in progress" end
        local prepared, reason = self.model:Validate(profile, true)
        if not prepared then return false, reason end
        if not allowed(prepared) then
            return false, "Profile enables unavailable runtime features"
        end
        local accepted, failure = applyPrepared(prepared, true, "Applied choices; session paused")
        if accepted then
            self.currentProfile, self.profileModified = self.staged == profile and self.stagedName or nil, false
            self:Refresh()
        end
        return accepted, failure
    end

    function self:SaveProfile(name)
        if not self.alive or not self.profileStore then
            return false, "Profile storage unavailable"
        end
        local saved, reason = self.profileStore:Save(
            name, self.model:Snapshot())
        if saved then
            self.currentProfile, self.profileModified = name, false
            if self.ui.profiles then self.ui.profiles:RefreshStorage() end
            self:Refresh("Saved profile: " .. name)
        end
        return saved, reason
    end

    function self:PreviewProfile(name)
        if not self.alive or not self.profileStore then
            return false, "Profile storage unavailable"
        end
        local profile, reason = self.profileStore:Load(name)
        if not profile then return false, reason end
        local prepared
        prepared, reason = self.model:Validate(profile, true)
        if not prepared then return false, reason end
        self.staged = { schema = 1, values = prepared }
        self.stagedName = name
        self.ui.profileStatus:Set("Ready to apply: " .. name, true)
        return self:Refresh("Previewed saved profile")
    end

    local codec = dependencies.codec
    local transferAvailable = type(codec) == "table" and type(codec.Encode) == "function"
        and type(codec.Decode) == "function"

    local function showImportReview(review, staged)
        self.importReview = review
        if not review then self.importReviewText = ""; return true end
        review.note = "Unchanged legacy defaults use current reviewed defaults. Automation and new permissions are not enabled automatically. Apply is separate and pauses the session."
        review.status = staged and "Ready for explicit Apply" or "Unresolved; nothing staged"
        review.stagedPreview = nil
        if staged then
            local values = {}
            for key, value in pairs(staged.values) do values[key] = value end
            review.stagedPreview = { schema = 1, values = values }
        end
        local ok, text = pcall(codec.Encode, codec, review)
        if not ok or type(text) ~= "string" or #text > 65536 then
            self.importReviewText = "Import review could not be displayed within 64 KiB; original input retained. Nothing applied."
            return false
        end
        self.importReviewText = text
        return true
    end

    function self:ExportProfile()
        if not self.alive or not transferAvailable then return nil, "Settings JSON adapter unavailable" end
        local ok, text = pcall(codec.Encode, codec, self.model:Snapshot())
        if not ok or type(text) ~= "string" or #text > 65536 then
            return nil, "Settings export failed or exceeds 64 KiB"
        end
        return text, nil
    end

    function self:PreviewImport(text)
        if not self.alive or not transferAvailable then return false, "Settings JSON adapter unavailable" end
        if type(text) ~= "string" or #text == 0 or #text > 65536 then
            return false, "Settings JSON must contain 1–65536 bytes"
        end
        local ok, profile = pcall(codec.Decode, codec, text)
        if not ok then return false, "Settings JSON could not be decoded" end
        local legacy = type(profile) == "table" and (profile.version ~= nil or profile.settings ~= nil)
        if legacy then
            local migration = dependencies.LegacySettings
            if type(migration) ~= "table" or type(migration.preview) ~= "function" then
                return false, "Legacy settings preview unavailable"
            end
            local converted, review, reason = migration.preview(profile, self.model)
            self.importReview = review
            if not converted then
                showImportReview(review)
                self.staged, self.stagedName = nil, nil
                self.ui.profileStatus:Set(reason or "Legacy choices need review", true)
                self:Refresh("Legacy choices require review")
                return false, reason
            end
            profile = converted
        end
        local prepared, reason = self.model:Validate(profile, true)
        if not prepared then return false, reason end
        if not allowed(prepared) then return false, "Profile enables unavailable runtime features" end
        local values = {}
        for key, value in pairs(prepared) do values[key] = value end
        local staged = { schema = 1, values = values }
        if legacy and not showImportReview(self.importReview, staged) then
            self.staged, self.stagedName = nil, nil
            self.ui.profileStatus:Set("Import review unavailable; nothing staged", true)
            self:Refresh("Import review unavailable")
            return false, "Import review unavailable; nothing staged"
        end
        if not legacy then showImportReview(nil) end
        self.staged, self.stagedName = staged, nil
        self.ui.profileStatus:Set(legacy
            and "Ready to apply: legacy choices; defaults updated, automation off"
            or "Ready to apply: imported settings", true)
        return self:Refresh("Previewed imported choices")
    end

    function self:RenameProfile(name, replacement)
        if not self.alive or not self.profileStore then return false, "Profile storage unavailable" end
        local saved, reason = self.profileStore:Rename(name, replacement)
        if not saved then return false, reason end
        if self.currentProfile == name then self.currentProfile = replacement end
        if self.stagedName == name then
            self.stagedName = replacement
            self.ui.profileStatus:Set("Ready to apply: " .. replacement, true)
        end
        if self.ui.profiles then
            self.ui.profiles.profileName:Set(replacement, true)
            self.ui.profiles:RefreshStorage()
        end
        return self:Refresh("Renamed saved profile")
    end

    function self:SetAutoload(name)
        if not self.alive or not self.profileStore then
            return false, "Profile storage unavailable"
        end
        local saved, reason = self.profileStore:SetAutoload(name)
        if saved then
            if self.ui.profiles then self.ui.profiles:RefreshStorage() end
            self.ui:RecordActivity(name
                and ("Autoload on: " .. name) or "Autoload off")
        end
        return saved, reason
    end

    function self:SetNextLoad(name)
        if not self.alive or not self.profileStore then return false, "Profile storage unavailable" end
        local saved, reason = self.profileStore:SetNextLoad(name)
        if saved then
            if self.ui.profiles then self.ui.profiles:RefreshStorage() end
            self.ui:RecordActivity(name and ("Next launch only: " .. name) or "Next-launch choice cleared")
        end
        return saved, reason
    end

    function self:DeleteProfile(name)
        if not self.alive or not self.profileStore then return false, "Profile storage unavailable" end
        if not self.model.paused or self.stagedName ~= name then
            return false, "Pause and preview this saved profile before deletion"
        end
        local saved, reason = self.profileStore:Delete(name, self.staged)
        if saved then
            self.staged, self.stagedName = nil, nil
            if self.currentProfile == name then self.currentProfile, self.profileModified = nil, false end
            if self.ui.profiles then self.ui.profiles:RefreshStorage() end
            self.ui.profileStatus:Set("None", true)
            self:Refresh("Deleted saved profile: " .. name)
        end
        return saved, reason
    end

    function self:SetProfileSync(enabled)
        if not self.alive or not self.profileStore then return false, "Profile storage unavailable" end
        local saved, reason = self.profileStore:SetSync(enabled)
        if saved then self.profileSync, self.profileSyncError = enabled, nil
        else self.profileSyncError = reason end
        self:Refresh(saved and "Profile edit saving preference updated" or "Profile saving preference rejected")
        return saved, reason
    end

    function self:Set(key, value)
        if not self.alive then return false, "Prototype is closed" end
        if self.profileSaving then return false, "Profile save already in progress" end
        if not self.model.specs[key] or value == nil then return false, "Invalid preference: " .. tostring(key) end
        local prepared, reason = self.model:Validate({ schema = 1, values = { [key] = value } })
        if not prepared then return false, reason end
        if not allowed(prepared) then
            return false, "Feature unavailable in this runtime preview"
        end
        local previousModified = self.profileModified
        local changed = self.model.values[key] ~= value
        local syncing = changed and self.currentProfile and self.profileSync and self.profileStore
        local wasRunning = runtime and not self.model.paused and not self.model.stopped
        if self.currentProfile and changed then self.profileModified = true end
        if syncing then
            self.profileSaving = true
            if runtime then runtime:Pause() end
        end
        local accepted, failure = applyPrepared(prepared, false, "Changed " .. key)
        if not accepted then self.profileModified = previousModified
        elseif syncing then
            local saved, saveReason = self.profileStore:Save(self.currentProfile, self.model:Snapshot())
            if saved then self.profileModified, self.profileSyncError = false, nil
            else
                self.profileModified, self.profileSyncError = true, saveReason
                self.model:Pause()
                failure = "Choice is unsaved; profile save failed; session paused"
                accepted = false
            end
        end
        if syncing then
            self.profileSaving = false
            if self.alive then
                if wasRunning and not self.model.paused and not self.model.stopped then runtime:Resume() end
                self:Refresh(accepted and "Saved active-profile edit" or failure)
            end
        end
        return accepted, failure
    end

    function self:CanReplace()
        if self.profileSaving or self.profileStore and self.profileStore.writing then
            return false, "Profile storage is busy"
        end
        if not runtime then return true end
        if type(runtime.CanReplace)~="function" then return false,"Runtime replacement ownership unavailable" end
        return runtime:CanReplace()
    end
    function self:Pause()
        if not self.alive then return false, "Prototype is closed" end
        self.model:Pause()
        if runtime then runtime:Pause() end
        return self:Refresh("Paused")
    end
    function self:Resume()
        if not self.alive then return false, "Prototype is closed" end
        if runtime and type(runtime.FeatureRecoveryBusy) == "function" and runtime:FeatureRecoveryBusy() then
            return false, "Feature recovery is saving; wait before resuming"
        end
        if runtime and type(runtime.AllowanceResetBusy) == "function" and runtime:AllowanceResetBusy() then
            return false, "Allowance reset is saving; wait before resuming"
        end
        if runtime and runtime:Status().state == "stopped" then
            return false, "Automation stopped; reload required"
        end
        self.model:Resume()
        local ok, reason = self:Refresh(runtime and "Resumed automation" or "Resumed UI only")
        if ok and runtime then runtime:Resume() end
        return ok, reason
    end
    function self:PreviewAllowance(feature)
        self.allowanceStaged = nil
        if not self.alive or not runtime or type(runtime.PreviewAllowanceReset) ~= "function" then
            return nil, "Allowance controls need the connected runtime"
        end
        if not self.model.paused then return nil, "Pause automation before reviewing an allowance" end
        local preview, reason = runtime:PreviewAllowanceReset(feature)
        if preview then self.allowanceStaged = preview end
        return preview, reason
    end
    function self:CancelAllowancePreview()
        self.allowanceStaged = nil
        if runtime and type(runtime.CancelAllowanceReset) == "function" then runtime:CancelAllowanceReset() end
    end
    function self:ConfirmAllowance(feature)
        local staged = self.allowanceStaged
        self.allowanceStaged = nil
        if not self.alive or not self.model.paused or not staged or staged.feature ~= feature
            or not runtime or type(runtime.ConfirmAllowanceReset) ~= "function" then
            return false, "Pause and preview this allowance before confirming"
        end
        local saved, reason = runtime:ConfirmAllowanceReset(staged.ticket)
        if self.alive then self:Refresh(saved and "Reset local allowance" or "Allowance reset refused") end
        return saved, reason
    end
    function self:PreviewFeatureRecovery(feature)
        self.featureRecoveryStaged = nil
        if not self.alive or not self.model.paused or not runtime
            or type(runtime.PreviewFeatureRecovery) ~= "function" then return nil, "Pause the connected runtime before reviewing recovery" end
        local preview, reason = runtime:PreviewFeatureRecovery(feature)
        if preview then self.featureRecoveryStaged = {feature = feature, ticket = preview.ticket} end
        return preview, reason
    end
    function self:ConfirmFeatureRecovery(feature)
        local staged = self.featureRecoveryStaged
        self.featureRecoveryStaged = nil
        if not self.alive or not self.model.paused or not staged or staged.feature ~= feature
            or not runtime or type(runtime.ConfirmFeatureRecovery) ~= "function" then return false, "Pause and review this recovery before confirming" end
        local saved, reason = runtime:ConfirmFeatureRecovery(feature, staged.ticket)
        if self.alive then self:Refresh(saved and "Updated local recovery records; automation remains paused" or "Recovery refused") end
        return saved, reason
    end
    function self:Stop()
        if not self.alive then return false, "Prototype is closed" end
        self.model:Stop()
        if self.currentProfile then self.profileModified = true end
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
                    selectedJobId = self.model.values["jobs.custom.selectedJobId"],
                    limitsEnabled = self.model.values["jobs.custom.limitsEnabled"],
                    city = self.model.values["jobs.custom.city"],
                    masteryTarget = self.model.values["jobs.custom.masteryTarget"],
                    energyReserve = self.model.values["shared.energyReserve"],
                    minLevel = self.model.values["jobs.custom.minLevel"], maxLevel = self.model.values["jobs.custom.maxLevel"],
                    minCost = self.model.values["jobs.custom.minCost"], maxCost = self.model.values["jobs.custom.maxCost"] },
                operations = { enabled = enabled
                    and self.model.values["operations.enabled"] == true,
                    policy = self.model.values["operations.policy"],
                    selection = self.model.values["operations.custom.selection"],
                    selectedIds = self.model.values["operations.custom.selectedIds"],
                    limitsEnabled = self.model.values["operations.custom.limitsEnabled"],
                    minLevel = self.model.values["operations.custom.minLevel"],
                    maxLevel = self.model.values["operations.custom.maxLevel"],
                    minHours = self.model.values["operations.custom.minHours"],
                    maxHours = self.model.values["operations.custom.maxHours"],
                    minCrateRarity = self.model.values["operations.custom.minCrateRarity"] },
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
                        and self.model.values["operations.enabled"] == true
                        and self.model.values["withdraw.custom.allowOperations"] == true,
                    allowSafehouse = enabled
                        and self.model.values["safehouse.enabled"] == true
                        and self.model.values["withdraw.custom.allowSafehouse"] == true,
                    allowHeists = enabled
                        and self.model.values["heists.enabled"] == true
                        and self.model.values["withdraw.custom.allowHeists"] == true,
                    allowProperties = enabled
                        and self.model.values["properties.enabled"] == true
                        and self.model.values["withdraw.custom.allowProperties"] == true,
                    allowShop = enabled and self.model.values["shop.enabled"] == true
                        and self.model.values["withdraw.custom.allowShop"] == true },
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
            for _, id in ipairs({"combat", "warCombat", "sabotage"}) do
                if settings[id] then
                    settings[id].relationAllies = self.model.values["alliance.allies"]
                    settings[id].relationEnemies = self.model.values["alliance.enemies"]
                    settings[id].enemyMode = self.model.values["alliance.mode"]
                end
            end
            settings.alliance = {browse = enabled and self.model.values["alliance.browse"] == true,
                query = self.model.values["alliance.query"]}
            if settings.combat then
                settings.combat.preferHighValue = self.model.values["combat.memory.preferHighValue"]
                settings.combat.highPromoteCash = self.model.values["combat.memory.promoteCash"]
                settings.combat.highDemoteBelow = self.model.values["combat.memory.demoteBelow"]
                settings.combat.highDemoteHits = self.model.values["combat.memory.demoteHits"]
            end
            for id in pairs(energyActivities) do
                if settings[id] then settings[id].energyReserve = self.model.values["shared.energyReserve"] or 0 end
            end
            if type(allowedFeatures) == "table" then
                for id, feature in pairs(settings) do
                    if allowedFeatures[id] ~= true then feature.enabled = false end
                end
            end
        else
            settings = { enabled = enabled
                and self.model.values["jobs.enabled"] == true,
                policy = self.model.values["jobs.policy"],
                selectedJobId = self.model.values["jobs.custom.selectedJobId"],
                    limitsEnabled = self.model.values["jobs.custom.limitsEnabled"],
                    city = self.model.values["jobs.custom.city"],
                    masteryTarget = self.model.values["jobs.custom.masteryTarget"],
                    energyReserve = self.model.values["shared.energyReserve"],
                    minLevel = self.model.values["jobs.custom.minLevel"], maxLevel = self.model.values["jobs.custom.maxLevel"],
                    minCost = self.model.values["jobs.custom.minCost"], maxCost = self.model.values["jobs.custom.maxCost"] }
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
            self.stagedName = nil
            self.ui.profileStatus:Set("Staged locally", true)
            self:Refresh("Staged current choices")
        elseif name == "discard" then
            self.staged = nil
            self.stagedName = nil
            self.ui.profileStatus:Set("None", true)
            self:Refresh("Discarded staged choices")
        elseif name == "apply" then
            local ok, reason = self:ApplyProfile(self.staged)
            if not ok then self.ui.lastError = reason; self:Refresh("Profile not applied") end
        elseif name == "enableProfileSync" or name == "disableProfileSync" then
            local ok, reason = self:SetProfileSync(name == "enableProfileSync")
            if not ok then self.ui.lastError = reason end
        elseif name == "clearNextLoad" then
            local ok, reason = self:SetNextLoad(nil)
            if not ok then self.ui.lastError = reason; self:Refresh("Next-launch choice rejected") end
        elseif name == "disableAutoload" then
            local ok, reason = self:SetAutoload(nil)
            if not ok then self.ui.lastError = reason
                self:Refresh("Autoload setting rejected") end
        elseif name == "reviewSavedState" then self:ReviewSavedState()
        elseif name == "savedStateNext" or name == "savedStatePrevious" then
            if self.savedStateReview then
                local pages = math.max(1, math.ceil(#self.savedStateReview.rows / 6))
                self.savedStatePage = math.max(1, math.min(pages, (self.savedStatePage or 1)
                    + (name == "savedStateNext" and 1 or -1)))
                self:Refresh()
            end
        elseif name == "refreshProfiles" then
            self.ui.profiles:RefreshStorage()
        elseif name == "exportProfile" or name == "importProfile" then
            local field = self.ui.profiles and self.ui.profiles.transferText
            if not field then return end
            local ok, reason
            if name == "exportProfile" then
                local text
                text, reason = self:ExportProfile()
                if text then ok, reason = field:Set(text, true) end
                if ok then self:Refresh("Exported choices to text") end
            else
                local read, text = pcall(field.Get, field)
                if read then ok, reason = self:PreviewImport(text)
                else reason = "Settings text unavailable" end
            end
            if not ok then self.ui.lastError = reason or "Settings transfer failed"
                self:Refresh("Settings transfer rejected") end
        elseif name == "saveProfile" or name == "previewProfile"
            or name == "enableAutoload" or name == "renameProfile"
            or name == "nextLoadProfile" or name == "deleteProfile" then
            if not self.ui.profileName then return end
            local read, profileName = pcall(self.ui.profileName.Get,
                self.ui.profileName)
            local ok, reason
            if not read then
                ok, reason = false, "Profile name unavailable"
            elseif name == "saveProfile" then
                ok, reason = self:SaveProfile(profileName)
            elseif name == "previewProfile" then
                ok, reason = self:PreviewProfile(profileName)
            elseif name == "nextLoadProfile" then
                ok, reason = self:SetNextLoad(profileName)
            elseif name == "deleteProfile" then
                ok, reason = self:DeleteProfile(profileName)
            elseif name == "renameProfile" then
                local readName, replacement = pcall(self.ui.profiles.renameName.Get,
                    self.ui.profiles.renameName)
                if readName then ok, reason = self:RenameProfile(profileName, replacement)
                else reason = "Replacement name unavailable" end
            else
                ok, reason = self:SetAutoload(profileName)
            end
            if not ok then self.ui.lastError = reason
                self:Refresh("Profile operation rejected") end
        end
    end

    local created, uiOrReason = pcall(dependencies.EmberAdapter.new,
        dependencies.Ember, dependencies.Catalog, {
        change = change, command = command, destroy = closed,
        profileStorage = self.profileStore ~= nil,
        savedStateReviewAvailable = savedStateReader ~= nil,
        savedStateReviewUnavailable = savedStateUnavailable,
        profileTransfer = transferAvailable,
        profileOverview = self.profileStore and function() return self.profileStore:AccountOverview() end or nil,
        profileSummary = self.profileStore and function()
            local names, listReason = self.profileStore:List()
            if not names then return nil, nil, listReason end
            local autoload, autoloadReason = self.profileStore:GetAutoload()
            local nextLoad, nextReason = self.profileStore:GetNextLoad()
            return names, autoload, autoloadReason,
                nextReason and ("Unavailable: " .. nextReason) or nextLoad
        end or nil,
        runtimeConnected = runtime ~= nil,
        prestigeResetAvailable = (type(allowedFeatures) ~= "table" or allowedFeatures.prestige == true)
            and runtime ~= nil and type(runtime.SupportsPrestigeReset) == "function" and runtime:SupportsPrestigeReset(),
        allowanceAvailable = runtime ~= nil and type(runtime.SupportsAllowanceReset) == "function" and runtime:SupportsAllowanceReset(),
        allowancePreview = function(feature) return self:PreviewAllowance(feature) end,
        allowanceConfirm = function(feature) return self:ConfirmAllowance(feature) end,
        allowanceCancel = function() return self:CancelAllowancePreview() end,
        featureAvailable = function(feature)
            return (type(allowedFeatures) ~= "table" or allowedFeatures[feature] == true)
                and runtime ~= nil and type(runtime.SupportsFeature) == "function" and runtime:SupportsFeature(feature)
        end,
        featureRecoveryAvailable = function(feature)
            return runtime ~= nil and type(runtime.SupportsFeatureRecovery) == "function" and runtime:SupportsFeatureRecovery(feature)
        end,
        featureRecoveryPreview = function(feature) return self:PreviewFeatureRecovery(feature) end,
        featureRecoveryConfirm = function(feature) return self:ConfirmFeatureRecovery(feature) end,
        allowedFeatures = allowedFeatures,
        overviewModule = dependencies.OverviewTab,
        playerModule = dependencies.PlayerTab,
        allianceModule = dependencies.AllianceTab,
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
    local ok, reason = self:Refresh(startupNote)
    if not ok then self:Destroy(); error(reason, 0) end
    if runtime then runtime:Resume() end
    return self
end

return App
