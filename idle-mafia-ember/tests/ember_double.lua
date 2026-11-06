-- Contract double only: does not emulate Roblox layout or render Ember.
Vector2 = { new = function(x, y) return { X = x, Y = y } end }
Enum = { KeyCode = { F8 = "F8" } }

return function()
    local ember = { queue = {}, windows = {}, configured = nil }
    function ember.Configure(options) ember.configured = options end
    function ember.ThemeNames() return { "Midnight", "Dark", "Slate" } end
    function ember.SetTheme(name) ember.theme = name end
    function ember.Flush(reverse)
        local pending = ember.queue
        ember.queue = {}
        if reverse then
            for i = #pending, 1, -1 do pending[i]() end
        else
            for _, callback in ipairs(pending) do callback() end
        end
    end
    function ember.new(options)
        for _, old in ipairs(ember.windows) do
            if old.options.Name == options.Name and not old.destroyed then old:Destroy() end
        end
        local window = { options = options, sections = {}, handles = {}, listeners = {} }
        local function container(label)
            local box = { label = label, groups = {} }
            function box:Description(_) end
            function box:Title(_) end
            function box:Group(opts)
                local group = container(opts.Text)
                group.visible = opts.Open ~= false
                function group:SetVisible(on) self.visible = on end
                self.groups[#self.groups + 1] = group
                return group
            end
            local function control(kind, opts)
                if ember.failLabel == opts.Text then error("construction failed") end
                local handle = { value = opts.Default, kind = kind, options = opts, visible = true }
                handle.throwNext = ember.throwSetLabel == opts.Text
                function handle:Get() return self.value end
                function handle:Set(value, silent)
                    if self.rejectAll or value == self.reject then return false, "refused" end
                    if self.throwNext then self.throwNext = false; error("setter failed") end
                    self.value = value
                    if not silent and opts.Callback then
                        ember.queue[#ember.queue + 1] = function() opts.Callback(value) end
                    end
                    return true
                end
                function handle:SetVisible(on) self.visible = on end
                function handle:SetOptions(options, silent)
                    self.options.Options = options
                    if self.kind == "Dropdown" then
                        local found = false
                        for _, option in ipairs(options) do
                            if option == self.value then found = true; break end
                        end
                        if not found then
                            self.value = options[1]
                            if not silent and opts.Callback then
                                ember.queue[#ember.queue + 1] = function()
                                    opts.Callback(self.value)
                                end
                            end
                        end
                    end
                    return true
                end
                function handle:SetDisabled(on) self.disabled = on end
                function handle:Click()
                    ember.queue[#ember.queue + 1] = opts.Callback
                end
                window.handles[#window.handles + 1] = handle
                if opts.Callback and (opts.FireOnStart or ember.forceInitial) then
                    ember.queue[#ember.queue + 1] = function()
                        opts.Callback(handle.value, nil, { initial = true, restored = true })
                    end
                end
                return handle
            end
            for _, kind in ipairs({ "Toggle", "Dropdown", "Input", "Status", "Button" }) do
                box[kind] = function(_, opts) return control(kind, opts) end
            end
            return box
        end
        function window:Section(label, icon)
            local section = container(label)
            section.icon = icon
            self.sections[#self.sections + 1] = section
            return section
        end
        function window:OnDestroy(callback) self.listeners[#self.listeners + 1] = callback end
        function window:Destroy()
            if self.destroyed then return false end
            self.destroyed = true
            for _, callback in ipairs(self.listeners) do callback() end
            return true
        end
        ember.windows[#ember.windows + 1] = window
        return window
    end
    return ember
end
