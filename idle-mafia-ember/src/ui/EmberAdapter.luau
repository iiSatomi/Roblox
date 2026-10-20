-- Actual Ember API boundary. All callbacks are local application commands.
local Adapter = {}
Adapter.__index = Adapter

local ICONS = {
    overview = "house", heists = "lock", jobs = "briefcase", operations = "clock",
    favors = "handshake", combat = "swords", crew = "users", inventory = "backpack",
    collection = "library", money = "wallet", property = "building", safehouse = "house",
    prestige = "trending-up", shop = "shopping-cart", blackMarket = "store",
    family = "users", territory = "map", contracts = "clipboard-list", trophies = "trophy",
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
    }, Adapter)
    ember.Configure({
        Storage = false,
        Themes = { Default = "Midnight" },
        Effects = { RespectReducedMotion = true, Quality = "Low" },
    })
    self.window = ember.new({
        Name = "IdleMafiaEmberPrototype", Title = "Idle Mafia", Subtitle = "Ember UI prototype 0.1",
        Size = Vector2.new(920, 620), MinSize = Vector2.new(640, 420), Rail = 184,
        Keybind = Enum.KeyCode.F8, Search = true, SaveLayout = false,
        ReapplyOnRespawn = false, ReplaceExisting = true,
        StatusBar = { Text = "UI prototype only — no gameplay connected" },
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
        overview:Description({ Text = "Local UI preview. Feature choices do not start Jobs, fights or purchases." })
        self.sessionStatus = overview:Status({ Text = "Session", Default = "Paused — UI only" })
        button(overview, "Pause", "pause")
        button(overview, "Resume", "resume")
        button(overview, "Emergency Stop", "stop", true)
        button(overview, "Unload", "unload", true)

        for _, feature in ipairs(catalog.features) do
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
            local row = { feature = feature,
                status = group:Status({ Text = "Activity", Default = "Off — UI only" }) }
            self.features[feature.id] = row
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

        sections.profiles:Description({ Text = "Stage and reapply choices in memory. No account files are read or written. Applying pauses the prototype." })
        self.profileStatus = sections.profiles:Status({ Text = "Staged profile", Default = "None" })
        button(sections.profiles, "Stage current choices", "stage")
        button(sections.profiles, "Apply staged choices", "apply")
        button(sections.profiles, "Discard staged choices", "discard")
        sections.settings:Dropdown({ Text = "Theme", Options = ember.ThemeNames(), Default = "Midnight",
            Save = false, FireOnStart = false, Callback = function(value, _, origin)
                if self.alive and userOrigin(origin) then ember.SetTheme(value) end
            end })
        sections.settings:Description({ Text = "F8 shows or hides this window. Reduced motion is enabled; appearance is not saved." })
        self.activity = sections.activity:Status({ Text = "Latest local command", Default = "Created inert UI" })
        self.errorStatus = sections.activity:Status({ Text = "UI validation", Default = "No errors" })
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

function Adapter:Render(model)
    local ok, reason = self:ApplyValues(model.values)
    if not ok then return false, reason end
    local session = model.stopped and "Stopped" or (model.paused and "Paused" or "Resumed")
    self.sessionStatus:Set(session .. " — UI only; gameplay disconnected", true)
    for id, row in pairs(self.features) do
        local selected = model.values[id .. ".enabled"]
        local label = "Off"
        if selected then label = model.stopped and "Stopped" or (model.paused and "Paused" or "Selected") end
        row.status:Set(label .. " — UI only", true)
        if row.custom then row.custom:SetVisible(model.values[id .. ".policy"] == "Custom") end
    end
    self.errorStatus:Set(self.lastError or "No errors", true)
    return true, nil
end

function Adapter:Destroy()
    self.alive = false
    return self.window:Destroy()
end

return Adapter
