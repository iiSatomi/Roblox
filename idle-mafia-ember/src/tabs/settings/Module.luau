-- Appearance controls for the inert preview. Gameplay permissions live with their tabs.
local SettingsTab = {}

function SettingsTab.new(section, ember, userOrigin, alive)
    assert(type(section) == "table" and type(ember) == "table"
        and type(ember.ThemeNames) == "function"
        and type(ember.SetTheme) == "function"
        and type(userOrigin) == "function" and type(alive) == "function",
        "Missing Settings UI dependencies")
    local theme = section:Dropdown({
        Text = "Theme", Options = ember.ThemeNames(), Default = "Midnight",
        Save = false, FireOnStart = false, Reapply = false,
        Callback = function(value, _, origin)
            if alive() and userOrigin(origin) then ember.SetTheme(value) end
        end,
    })
    section:Description({
        Text = "F8 shows or hides this window. Reduced motion is enabled; appearance is not saved.",
    })
    return { tabOwned = true, theme = theme }
end

return SettingsTab
