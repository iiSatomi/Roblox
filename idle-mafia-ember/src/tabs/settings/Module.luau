-- Appearance and current-session information. Gameplay permissions live with their tabs.
local SettingsTab = {}

function SettingsTab.new(section, ember, userOrigin, alive, callbacks, window)
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
    local modeStatus = windowGroup:Status({ Text = "Connection mode",
        Default = callbacks and callbacks.runtimeConnected
            and "Runtime attached — check each feature status"
            or "UI only — actions disconnected" })
    local theme = appearance:Dropdown({
        Text = "Theme", Options = names, Default = defaultTheme,
        Save = false, FireOnStart = false, Reapply = false,
        Callback = function(value, _, origin)
            if alive() and userOrigin(origin) then
                ember.SetTheme(value)
                themeStatus:Set(value, true)
            end
        end,
    })
    appearance:Button({ Text = "Reset theme", ButtonText = "Reset",
        FireOnStart = false, Callback = function(_, _, origin)
            if not alive() or not userOrigin(origin) then return end
            ember.SetTheme(defaultTheme)
            theme:Set(defaultTheme, true)
            themeStatus:Set(defaultTheme, true)
        end })
    windowGroup:Button({ Text = "Center window", ButtonText = "Center",
        FireOnStart = false, Callback = function(_, _, origin)
            if alive() and userOrigin(origin) and window then window:Center() end
        end })
    windowGroup:Description({
        Text = "F8 shows or hides the window. Use the search box to find a control. Theme changes last for this session only; reduced motion is enabled.",
    })
    return { tabOwned = true, theme = theme,
        themeStatus = themeStatus, modeStatus = modeStatus }
end

return SettingsTab
