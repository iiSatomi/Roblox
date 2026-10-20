-- Inert composition. No game services, remote calls, timers or account files.
local App = {}

function App.start(dependencies)
    local self = { alive = true, model = dependencies.Settings.new(dependencies.Catalog) }

    local function closed()
        self.alive = false
        self.model:Stop()
    end

    local function render(view, command)
        return pcall(function()
            local accepted, reason = self.ui:Render(view)
            if accepted and command then self.ui.activity:Set(command, true) end
            return accepted, reason
        end)
    end

    function self:Refresh(command)
        if not self.alive then return false, "Prototype is closed" end
        local ok, accepted, reason = render(self.model, command)
        if not ok or accepted == false then
            self.model:Pause()
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
                self.ui:Fail(failure)
            end
            return false, failure
        end
        self.model:Commit(values, pause)
        return true, nil
    end

    function self:ApplyProfile(profile)
        if not self.alive then return false, "Prototype is closed" end
        local prepared, reason = self.model:Validate(profile)
        if not prepared then return false, reason end
        return applyPrepared(prepared, true, "Applied choices; session paused")
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
        return self:Refresh("Paused")
    end
    function self:Resume()
        if not self.alive then return false, "Prototype is closed" end
        self.model:Resume()
        return self:Refresh("Resumed UI only")
    end
    function self:Stop()
        if not self.alive then return false, "Prototype is closed" end
        self.model:Stop()
        return self:Refresh("Stopped; choices cleared")
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
        end
    end

    self.ui = dependencies.EmberAdapter.new(dependencies.Ember, dependencies.Catalog, {
        change = change, command = command, destroy = closed,
    })
    local ok, reason = self:Refresh("Created inert UI")
    if not ok then self:Destroy(); error(reason, 0) end
    return self
end

return App
