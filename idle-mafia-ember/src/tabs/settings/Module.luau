-- Appearance and current-session information. Gameplay permissions live with their tabs.
local SettingsTab = {}

function SettingsTab.new(section, ember, userOrigin, alive, callbacks, window, preferences)
    assert(type(section) == "table" and type(ember) == "table"
        and type(ember.ThemeNames) == "function"
        and type(ember.SetTheme) == "function"
        and type(userOrigin) == "function" and type(alive) == "function",
        "Missing Settings UI dependencies")
    local names = ember.ThemeNames()
    local defaultTheme = "Midnight"
    local appearance = section:Group({ Text = "Appearance", Open = true })
    local windowGroup = section:Group({ Text = "Window", Open = true })
    local themeStatus = appearance:Status({ Text = "Current theme",
        Default = defaultTheme })
    local themeUpdate = appearance:Status({ Text = "Theme update", Default = "No changes" })
    local modeStatus = windowGroup:Status({ Text = "Connection mode",
        Default = callbacks and callbacks.runtimeConnected
            and "Runtime attached â€” check each feature status"
            or "UI only â€” actions disconnected" })
    local view = { tabOwned = true, themeStatus = themeStatus, themeUpdate = themeUpdate,
        modeStatus = modeStatus }
    if preferences and type(preferences.bind) == "function" and type(preferences.numeric) == "table" then
        local reserves = section:Group({ Text = "Shared energy reserve", Open = false })
        reserves:Description({ Text = "Applies to Jobs, Heist starts, Favor help and sabotage. A larger feature reserve still wins. This setting never enables an activity." })
        for _, field in ipairs(preferences.fields or {}) do
            assert(field.type == "number", "Unsupported shared reserve control")
            local key = "shared." .. field.id
            preferences.numeric[key] = true
            preferences.bind(reserves, "Input", key, { Text = field.label, Default = tostring(field.value), FireOnBlur = true })
        end
    end
    local theme, appliedTheme = nil, defaultTheme
    local function applyTheme(value)
        local ok, accepted, reason = pcall(ember.SetTheme, value)
        if not ok or accepted == false then
            view.lastError = ok and (reason or "Theme change refused") or "Theme change failed"
            themeUpdate:Set("Unchanged â€” " .. tostring(view.lastError), true)
            pcall(theme.Set, theme, appliedTheme, true)
            return false
        end
        view.lastError, appliedTheme = nil, value
        themeStatus:Set(value, true)
        themeUpdate:Set("Applied", true)
        return true
    end
    theme = appearance:Dropdown({
        Text = "Theme", Options = names, Default = defaultTheme,
        Save = false, FireOnStart = false, Reapply = false,
        Callback = function(value, _, origin)
            if alive() and userOrigin(origin) then
                local ok, current = pcall(theme.Get, theme)
                if ok and current == value then applyTheme(value) end
            end
        end,
    })
    appearance:Button({ Text = "Reset theme", ButtonText = "Reset",
        FireOnStart = false, Callback = function(_, _, origin)
            if not alive() or not userOrigin(origin) then return end
            if applyTheme(defaultTheme) then theme:Set(defaultTheme, true) end
        end })
    windowGroup:Button({ Text = "Center window", ButtonText = "Center",
        FireOnStart = false, Callback = function(_, _, origin)
            if alive() and userOrigin(origin) and window then window:Center() end
        end })
    windowGroup:Description({
        Text = "F8 shows or hides the window. Use the search box to find a control. Theme changes last for this session only; reduced motion is enabled.",
    })
    local targets = { ["Owned chests"] = "chests", ["Event Shop"] = "eventShop", ["Family Cash"] = "familyCash",
        ["Family Gold"] = "familyGold", ["Family Stamina"] = "familyStamina", ["Market rental"] = "marketRent",["Crew hires"]="crewHire", ["Crew stationing"] = "station", ["Residence requests"] = "residency" }
    local units = {chests = "crates",eventShop = "medals", familyCash = "Cash", familyGold = "Gold", familyStamina = "Stamina", marketRent = "Gold",crewHire="Cash", station="resources", residency="resources"}
    local available = callbacks and callbacks.allowanceAvailable == true
        and type(callbacks.allowancePreview) == "function" and type(callbacks.allowanceConfirm) == "function"
    local allowances = section:Group({Text = "Run allowances", Open = false, Disabled = not available,
        DisabledReason = "Allowance reset needs a compatible runtime"})
    allowances:Description({Text = "Pause first, review counted use, then confirm a fresh allowance. Configured limits stay unchanged. Pending actions or saved transactions must be resolved first."})
    local status = allowances:Status({Text = "Allowance review", Save = false, FireOnStart = false,
        Default = available and "Pause and review a feature" or "Allowance controls unavailable in this entry"})
    local selected, selection = "Event Shop", nil
    local function cancel()
        if callbacks and type(callbacks.allowanceCancel) == "function" then callbacks.allowanceCancel() end
    end
    local function currentTarget()
        local ok, label = pcall(selection.Get, selection)
        if not ok or not targets[label] then return nil end
        if label ~= selected then selected = label; cancel() end
        return targets[label]
    end
    selection = allowances:Dropdown({Text = "Allowance", Options = {"Owned chests", "Event Shop", "Family Cash", "Family Gold", "Family Stamina", "Market rental", "Crew hires", "Crew stationing", "Residence requests"},
        Default = selected, Save = false, FireOnStart = false, Reapply = false,
        Callback = function(value, _, origin)
            if not alive() or not userOrigin(origin) then return end
            local ok, current = pcall(selection.Get, selection)
            if ok and current == value and selected ~= value then
                selected = value; cancel(); status:Set("Review this allowance before confirming", true)
            end
        end})
    allowances:Button({Text = "Review allowance", ButtonText = "Review", FireOnStart = false,
        Callback = function(_, _, origin)
            if not alive() or not userOrigin(origin) or not available then return end
            local feature = currentTarget()
            if not feature then return end
            local ok, preview, reason = pcall(callbacks.allowancePreview, feature)
            if not alive() then return end
            if ok and type(preview) == "table" and preview.feature == feature and preview.unknown == true then
                status:Set("Previous chest use is unknown. Confirm to begin a fresh local allowance; this does not establish past consumption.", true)
            elseif ok and type(preview) == "table" and preview.feature == feature then
                status:Set(tostring(preview.attempted) .. " counted attempts; " .. tostring(preview.spent)
                    .. " counted " .. units[feature] .. ". Confirm to clear this local allowance.", true)
            else status:Set(ok and (reason or "Allowance review unavailable") or "Allowance review failed", true) end
        end})
    allowances:Button({Text = "Confirm allowance reset", ButtonText = "Confirm reset", Danger = true, FireOnStart = false,
        Callback = function(_, _, origin)
            if not alive() or not userOrigin(origin) or not available then return end
            local feature = currentTarget()
            if not feature then return end
            local ok, saved, reason = pcall(callbacks.allowanceConfirm, feature)
            if not alive() then return end
            status:Set(ok and saved == true and "Local allowance cleared; automation remains paused"
                or (ok and (reason or "Allowance reset refused") or "Allowance reset failed"), true)
        end})
    view.allowanceSelection, view.allowanceStatus = selection, status
    view.theme = theme
    return view
end

return SettingsTab
