-- Profile staging and account-scoped save/preview controls.
local ProfilesTab = {}
local Methods = {}
Methods.__index = Methods

function Methods:Render(model)
    local enabled = 0
    for key, value in pairs(model.values or {}) do
        if type(key) == "string" and key:sub(-8) == ".enabled"
            and value == true then enabled = enabled + 1 end
    end
    self.selectionStatus:Set(tostring(enabled) .. " selected", true)
    local staged = model.staged and model.staged.values
    if not staged then
        self.differenceStatus:Set("No staged choices", true)
        return
    end
    local changes = 0
    for key, value in pairs(staged) do
        if model.values[key] ~= value then changes = changes + 1 end
    end
    self.differenceStatus:Set(tostring(changes)
        .. (changes == 1 and " change" or " changes")
        .. " from current", true)
end

function Methods:RefreshStorage()
    if not self.profileSummary then return end
    local names, autoload, reason = self.profileSummary()
    if reason then
        self.storageStatus:Set("Unavailable — " .. reason, true)
        self.autoloadStatus:Set("Unavailable", true)
        self.savedSelection:SetOptions({ "Choose saved profile" }, true)
        return
    end
    local choices = { "Choose saved profile" }
    for _, name in ipairs(names) do choices[#choices + 1] = name end
    self.savedSelection:SetOptions(choices, true)
    local visible = {}
    for index = 1, math.min(#names, 3) do
        visible[#visible + 1] = names[index]
    end
    local suffix = #names > 3 and (" +" .. tostring(#names - 3) .. " more") or ""
    self.storageStatus:Set(#names == 0 and "No saved profiles"
        or (tostring(#names) .. " saved: " .. table.concat(visible, ", ") .. suffix), true)
    self.autoloadStatus:Set(autoload or "Off", true)
end

function ProfilesTab.new(section, callbacks, userOrigin)
    assert(type(section) == "table" and type(callbacks) == "table"
        and type(callbacks.command) == "function"
        and type(userOrigin) == "function",
        "Missing Profiles UI dependencies")
    section:Description({ Text = callbacks.profileStorage
        and "Profiles are saved for this account and place. Preview stages choices; Apply pauses the session so you can review before resuming."
        or "Stage and apply choices in this session. Reloading clears them. Apply leaves the UI paused." })
    local sessionGroup = section:Group({ Text = "Session choices", Open = true })
    local savedGroup = callbacks.profileStorage
        and section:Group({ Text = "Saved profiles", Open = true }) or nil
    local result = setmetatable({ tabOwned = true,
        profileSummary = callbacks.profileSummary,
        profileStatus = sessionGroup:Status({ Text = "Staged profile", Default = "None" }),
        selectionStatus = sessionGroup:Status({ Text = "Current choices", Default = "0 selected" }),
        differenceStatus = sessionGroup:Status({ Text = "Staged differences",
            Default = "No staged choices" }),
        storageStatus = (savedGroup or sessionGroup):Status({ Text = "Saved profiles",
            Default = callbacks.profileStorage and "Loading" or "Memory only" }),
    }, Methods)
    local function button(container, label, command)
        container:Button({ Text = label, ButtonText = label,
            FireOnStart = false, Callback = function(_, _, origin)
                if userOrigin(origin) then callbacks.command(command) end
            end })
    end
    if callbacks.profileStorage then
        savedGroup:Description({ Text = "Names use letters, numbers, _ or - (up to 32 characters). Save up to 16 profiles." })
        result.autoloadStatus = savedGroup:Status({ Text = "Autoload on next launch",
            Default = "Loading" })
        result.profileName = savedGroup:Input({
            Text = "Profile name", Default = "main",
            Save = false, FireOnStart = false,
            FireOnBlur = false, Reapply = false,
        })
        result.savedSelection = savedGroup:Dropdown({
            Text = "Choose saved profile",
            Options = { "Choose saved profile" },
            Default = "Choose saved profile", Save = false,
            FireOnStart = false, Reapply = false,
            Callback = function(name, _, origin)
                if userOrigin(origin) and name ~= "Choose saved profile" then
                    result.profileName:Set(name, true)
                end
            end,
        })
        button(savedGroup, "Save choices locally", "saveProfile")
        button(savedGroup, "Preview saved profile", "previewProfile")
        button(savedGroup, "Refresh saved profiles", "refreshProfiles")
        button(savedGroup, "Autoload this saved profile", "enableAutoload")
        button(savedGroup, "Disable autoload", "disableAutoload")
    end
    button(sessionGroup, "Stage current choices", "stage")
    button(sessionGroup, "Apply staged choices", "apply")
    button(sessionGroup, "Discard staged choices", "discard")
    result:RefreshStorage()
    return result
end

return ProfilesTab
