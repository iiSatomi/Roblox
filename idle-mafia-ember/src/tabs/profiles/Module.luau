-- Profile staging and account-scoped save/preview controls.
local ProfilesTab = {}

function ProfilesTab.new(section, callbacks, userOrigin)
    assert(type(section) == "table" and type(callbacks) == "table"
        and type(callbacks.command) == "function"
        and type(userOrigin) == "function",
        "Missing Profiles UI dependencies")
    section:Description({ Text = callbacks.profileStorage
        and "Save or preview local account choices. Preview does not activate them; applying pauses the session."
        or "Stage and reapply choices in memory. No account files are read or written. Applying pauses the prototype." })
    local result = { tabOwned = true,
        profileStatus = section:Status({ Text = "Staged profile",
            Default = "None" }) }
    local function button(text, command)
        section:Button({ Text = text, ButtonText = text,
            FireOnStart = false, Callback = function(_, _, origin)
                if userOrigin(origin) then callbacks.command(command) end
            end })
    end
    if callbacks.profileStorage then
        result.profileName = section:Input({
            Text = "Profile name", Default = "main",
            Save = false, FireOnStart = false,
            FireOnBlur = false, Reapply = false,
        })
        button("Save choices locally", "saveProfile")
        button("Preview saved profile", "previewProfile")
        button("Autoload this saved profile", "enableAutoload")
        button("Disable autoload", "disableAutoload")
    end
    button("Stage current choices", "stage")
    button("Apply staged choices", "apply")
    button("Discard staged choices", "discard")
    return result
end

return ProfilesTab
