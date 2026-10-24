-- Actual Ember API boundary. All callbacks are local application commands.
local Adapter = {}
Adapter.__index = Adapter

local ICONS = {
    overview = "home", heists = "lock", jobs = "briefcase", operations = "clock",
    favors = "handshake", combat = "swords", crew = "users", inventory = "backpack",
    collection = "library", money = "wallet", property = "building", safehouse = "shield",
    prestige = "trending-up", shop = "shopping-cart", blackMarket = "store",
    family = "users-round", territory = "map", contracts = "clipboard-list", trophies = "trophy",
    skills = "sparkles", rewards = "gift", events = "calendar", profiles = "folder",
    settings = "settings", activity = "activity",
}

local function userOrigin(origin)
    return not origin or not (origin.initial or origin.restored or origin.reapplied or origin.reverted)
end

function Adapter.new(ember, catalog, callbacks)
    local self = setmetatable({
        handles = {}, features = {}, numeric = {}, order = {}, alive = true,
        degraded = false, lastError = nil,
        allowedFeatures = callbacks.allowedFeatures,
    }, Adapter)
    ember.Configure({
        Storage = false,
        Themes = { Default = "Midnight" },
        Effects = { RespectReducedMotion = true, Quality = "Low" },
    })
    self.window = ember.new({
        Name = "IdleMafiaEmberPrototype", Title = "Idle Mafia", Subtitle = "Ember UI prototype 0.1.38",
        Size = Vector2.new(920, 620), MinSize = Vector2.new(640, 420), Rail = 184,
        Keybind = Enum.KeyCode.F8, Search = true, SaveLayout = false,
        ReapplyOnRespawn = false, ReplaceExisting = true,
        StatusBar = { Text = callbacks.runtimeConnected
            and "Runtime connected — features off until enabled"
            or "UI prototype only — no gameplay connected" },
    })
    -- Register teardown before constructing any value controls.
    self.window:OnDestroy(function()
        self.alive = false
        callbacks.destroy()
    end)

    local ok, reason = pcall(function()
        local sections = {}
        for _, page in ipairs(catalog.pages) do
            local section = self.window:Section(page.label, ICONS[page.id], { Search = true })
            sections[page.id] = section
            section:Description({ Text = page.description })
        end
        local function bind(container, kind, key, options)
            local handle
            options.Save = false
            options.FireOnStart = false
            options.Reapply = false
            options.Callback = function(value, _, origin)
                if self.alive and not self.degraded and userOrigin(origin) then
                    callbacks.change(key, value, handle)
                end
            end
            handle = container[kind](container, options)
            self.handles[key] = handle
            self.order[#self.order + 1] = key
            return handle
        end
        local function button(section, text, command, danger)
            section:Button({ Text = text, ButtonText = text, Danger = danger,
                FireOnStart = false, Callback = function(_, _, origin)
                    if self.alive and userOrigin(origin) then callbacks.command(command) end
                end })
        end

        local overview = sections.overview
        if callbacks.overviewModule then
            self.overview = callbacks.overviewModule.new(overview,
                callbacks, userOrigin)
            self.sessionStatus = self.overview.sessionStatus
        else
            overview:Description({ Text = callbacks.runtimeConnected
                and "Runtime connected. Feature switches start off; enabled actions run automatically."
                or "Local UI preview. Feature choices do not start Jobs, fights or purchases." })
            self.sessionStatus = overview:Status({ Text = "Session", Default = "Paused — UI only" })
            button(overview, "Pause", "pause")
            button(overview, "Resume", "resume")
            button(overview, "Emergency Stop", "stop", true)
            button(overview, "Unload", "unload", true)
        end

        for _, feature in ipairs(catalog.features) do
            local row
            if feature.page == "heists" and callbacks.heistsModule then
                row = callbacks.heistsModule.BuildUI(
                    sections.heists, feature, bind)
            elseif feature.page == "jobs" and callbacks.jobsModule then
                row = callbacks.jobsModule.BuildUI(
                    sections.jobs, feature, bind, function()
                        return self.alive and not self.degraded
                    end)
            elseif feature.page == "operations" and callbacks.operationsModule then
                row = callbacks.operationsModule.BuildUI(
                    sections.operations, feature, bind)
            elseif feature.page == "favors" and callbacks.favorsModule then
                row = callbacks.favorsModule.BuildUI(
                    sections.favors, feature, bind)
            elseif feature.page == "combat" and callbacks.combatModule then
                row = callbacks.combatModule.BuildUI(
                    sections.combat, feature, bind, self.numeric)
            elseif feature.page == "crew" and callbacks.crewModule then
                row = callbacks.crewModule.BuildUI(
                    sections.crew, feature, bind, self.numeric)
            elseif feature.page == "inventory" and callbacks.inventoryModule then
                row = callbacks.inventoryModule.BuildUI(
                    sections.inventory, feature, bind, self.numeric)
            elseif feature.page == "collection" and callbacks.collectionModule then
                row = callbacks.collectionModule.BuildUI(
                    sections.collection, feature, bind, self.numeric)
            elseif feature.page == "money" and callbacks.moneyModule then
                row = callbacks.moneyModule.BuildUI(
                    sections.money, feature, bind, self.numeric)
            elseif feature.page == "property" and callbacks.propertyModule then
                row = callbacks.propertyModule.BuildUI(
                    sections.property, feature, bind, self.numeric)
            elseif feature.page == "safehouse" and callbacks.safehouseModule then
                row = callbacks.safehouseModule.BuildUI(
                    sections.safehouse, feature, bind, self.numeric)
            elseif feature.page == "prestige" and callbacks.prestigeModule then
                row = callbacks.prestigeModule.BuildUI(
                    sections.prestige, feature, bind)
            elseif feature.page == "shop" and callbacks.shopModule then
                row = callbacks.shopModule.BuildUI(
                    sections.shop, feature, bind, self.numeric)
            elseif feature.page == "blackMarket" and callbacks.blackMarketModule then
                row = callbacks.blackMarketModule.BuildUI(
                    sections.blackMarket, feature, bind)
            elseif feature.page == "family" and callbacks.familyModule then
                row = callbacks.familyModule.BuildUI(
                    sections.family, feature, bind)
            elseif feature.page == "territory" and callbacks.territoryModule then
                row = callbacks.territoryModule.BuildUI(
                    sections.territory, feature, bind)
            elseif feature.page == "contracts" and callbacks.contractsModule then
                row = callbacks.contractsModule.BuildUI(
                    sections.contracts, feature, bind)
            elseif feature.page == "trophies" and callbacks.trophiesModule then
                row = callbacks.trophiesModule.BuildUI(
                    sections.trophies, feature, bind)
            elseif feature.page == "skills" and callbacks.skillsModule then
                row = callbacks.skillsModule.BuildUI(
                    sections.skills, feature, bind, self.numeric)
            elseif feature.page == "rewards" and callbacks.rewardsModule then
                row = callbacks.rewardsModule.BuildUI(
                    sections.rewards, feature, bind)
            elseif feature.page == "events" and callbacks.eventsModule then
                row = callbacks.eventsModule.BuildUI(
                    sections.events, feature, bind)
            else
                local group = sections[feature.page]:Group({
                    Text = feature.label, Description = feature.description, Open = true,
                })
                bind(group, "Toggle", feature.id .. ".enabled", {
                    Text = "Allow " .. feature.label, Description = "Select this activity for the prototype.",
                    Default = false, RevertOnClose = true, RevertTo = false,
                })
                if #feature.policies > 0 then
                    bind(group, "Dropdown", feature.id .. ".policy", {
                        Text = "Goal", Options = feature.policies, Default = feature.policies[1],
                    })
                end
                row = { feature = feature,
                    status = group:Status({ Text = "Activity", Default = "Off — UI only" }) }
                if feature.limits then group:Description({ Text = feature.limits }) end
                if #feature.custom > 0 then
                    row.custom = group:Group({ Text = "Custom limits", Open = false })
                    for _, field in ipairs(feature.custom) do
                        local key = feature.id .. ".custom." .. field.id
                        if field.type == "number" then
                            self.numeric[key] = true
                            bind(row.custom, "Input", key, {
                                Text = field.label, Default = tostring(field.value), FireOnBlur = true,
                            })
                        else
                            bind(row.custom, "Dropdown", key, {
                                Text = field.label, Default = field.value, Options = field.options,
                            })
                        end
                    end
                end
            end
            self.features[feature.id] = row
        end

        if callbacks.profilesModule then
            self.profiles = callbacks.profilesModule.new(
                sections.profiles, callbacks, userOrigin)
            self.profileStatus = self.profiles.profileStatus
            self.profileName = self.profiles.profileName
        else
            sections.profiles:Description({ Text = "Stage and apply choices locally; applying pauses the prototype." })
            self.profileStatus = sections.profiles:Status({ Text = "Staged profile", Default = "None" })
            button(sections.profiles, "Stage current choices", "stage")
            button(sections.profiles, "Apply staged choices", "apply")
            button(sections.profiles, "Discard staged choices", "discard")
        end
        if callbacks.settingsModule then
            self.settings = callbacks.settingsModule.new(
                sections.settings, ember, userOrigin,
                function() return self.alive end, callbacks, self.window)
        else
            sections.settings:Dropdown({ Text = "Theme", Options = ember.ThemeNames(), Default = "Midnight",
                Save = false, FireOnStart = false, Callback = function(value, _, origin)
                    if self.alive and userOrigin(origin) then ember.SetTheme(value) end
                end })
            sections.settings:Description({ Text = "F8 shows or hides this window. Reduced motion is enabled; appearance is not saved." })
        end
        if callbacks.activityModule then
            self.activityTab = callbacks.activityModule.new(sections.activity)
            self.activity = self.activityTab.activity
            self.errorStatus = self.activityTab.errorStatus
        else
            self.activity = sections.activity:Status({ Text = "Latest local command", Default = "Created inert UI" })
            self.errorStatus = sections.activity:Status({ Text = "UI validation", Default = "No errors" })
        end
        table.sort(self.order)
    end)
    if not ok then
        self.alive = false
        pcall(self.window.Destroy, self.window, true)
        error(reason, 0)
    end
    return self
end

function Adapter:ApplyValues(values)
    if not self.alive or self.degraded then return false, "UI is closed or needs reload" end
    local changed = {}
    for _, key in ipairs(self.order) do
        local value = values[key]
        if value ~= nil then -- Preserve explicit false; never use Ember:SetValues.
            if self.numeric[key] then value = tostring(value) end
            local handle = self.handles[key]
            local readOK, before = pcall(handle.Get, handle)
            local setOK, accepted, reason = readOK, true, nil
            if readOK and before ~= value then
                changed[#changed + 1] = { handle = handle, before = before }
                setOK, accepted, reason = pcall(handle.Set, handle, value, true)
            end
            if not readOK or not setOK or accepted == false then
                for i = #changed, 1, -1 do
                    local entry = changed[i]
                    local restored, result = pcall(entry.handle.Set, entry.handle, entry.before, true)
                    if not restored or result == false then self.degraded = true end
                end
                self.lastError = "UI refused " .. key .. ": " .. tostring(reason or accepted or before)
                if self.degraded then
                    self:Fail(self.lastError .. "; rollback failed, reload required")
                end
                return false, self.lastError
            end
        end
    end
    return true, nil
end

function Adapter:Fail(reason)
    self.degraded = true
    self.lastError = reason
    for _, input in pairs(self.handles) do pcall(input.SetDisabled, input, true, reason) end
    if self.errorStatus then pcall(self.errorStatus.Set, self.errorStatus, reason, true) end
end

function Adapter:RecordActivity(command)
    if self.activityTab then self.activityTab:Record(command)
    else self.activity:Set(command, true) end
end

function Adapter:Render(model)
    local ok, reason = self:ApplyValues(model.values)
    if not ok then return false, reason end
    local session = model.stopped and "Stopped" or (model.paused and "Paused" or "Resumed")
    local sessionDetail = " — UI only; gameplay disconnected"
    if model.automationRuntime then
        sessionDetail = " — shared broker adapter attached"
    elseif model.jobsRuntime then
        sessionDetail = " — Jobs adapter attached"
    end
    if self.overview then self.overview:Render(model)
    else self.sessionStatus:Set(session .. sessionDetail, true) end
    if self.profiles then self.profiles:Render(model) end
    for id, row in pairs(self.features) do
        local selected = model.values[id .. ".enabled"]
        local label = "Off"
        if selected then label = model.stopped and "Stopped" or (model.paused and "Paused" or "Selected") end
        if type(self.allowedFeatures) == "table"
            and self.allowedFeatures[id] ~= true then
            row.status:Set("Unavailable in this runtime preview", true)
        elseif row.blockedReason then
            row.status:Set("Blocked — " .. row.blockedReason, true)
        elseif model.automationRuntime
            and type(model.automationRuntime.availableFeatures) == "table"
            and model.automationRuntime.availableFeatures[id] == true then
            local runtime = model.automationRuntime
            local active = runtime.active
            local outcome = runtime.outcomes and runtime.outcomes[id]
            local featureReason = runtime.reasons and runtime.reasons[id]
            local uncertain = runtime.uncertainByFeature
                and runtime.uncertainByFeature[id] or 0
            if runtime.storageFault then
                label = "Blocked — checkpoint storage failed"
            elseif active and active.feature == id then
                label = "Awaiting exact state — " .. active.phase
            elseif uncertain > 0 then
                label = "Unconfirmed — duplicate risk; blocked"
            elseif not selected or model.stopped then
                label = label .. " — shared broker"
            elseif outcome == "confirmed" then
                label = "Last confirmed by replicated state"
            elseif outcome == "rejected" then
                label = "Last rejected by response"
            elseif active then
                label = "Waiting — broker busy"
            else
                label = "Waiting — " .. tostring(featureReason or runtime.reason or "fresh state")
            end
            row.status:Set(label, true)
        elseif id == "jobs" and model.jobsRuntime then
            local runtime = model.jobsRuntime
            if runtime.storageFault then
                label = "Blocked — checkpoint storage failed"
            elseif runtime.active then
                label = "Awaiting exact Job progress — " .. runtime.active.phase
            elseif runtime.uncertainCount > 0 then
                label = "Unconfirmed — duplicate risk; Jobs blocked"
            elseif runtime.lastOutcome == "confirmed" then
                label = "Confirmed by Job progress"
            elseif runtime.lastOutcome == "rejected" then
                label = "Rejected by response"
            elseif selected and not model.paused and not model.stopped then
                label = "Waiting — " .. tostring(runtime.reason or "fresh state")
            end
            row.status:Set(label, true)
        else
            row.status:Set(label .. " — UI only", true)
        end
        if row.custom then
            row.custom:SetVisible(#row.feature.policies == 0
                or model.values[id .. ".policy"] == (row.customPolicy or "Custom"))
        end
    end
    if self.activityTab then self.activityTab:Render(model, self.lastError)
    else self.errorStatus:Set(self.lastError or "No errors", true) end
    return true, nil
end

function Adapter:Destroy()
    self.alive = false
    return self.window:Destroy()
end

return Adapter
