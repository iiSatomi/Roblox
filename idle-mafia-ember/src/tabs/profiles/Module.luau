-- Profile staging and account-scoped save/preview controls.
local ProfilesTab = {}
local Methods = {}
Methods.__index = Methods

function Methods:Render(model)
    if self.importReviewText then self.importReviewText:Set(model.importReviewText or "", true) end
    if self.syncToggle then
        self.syncToggle:Set(model.profileSync == true, true)
        self.syncStatus:Set(model.profileSaving and "Saving edit"
            or model.profileSyncError and ("Unsaved: " .. model.profileSyncError)
            or model.profileSync and "Later edits save to the active profile"
            or "Manual: use Save choices locally", true)
    end
    self.appliedStatus:Set((model.currentProfile or "Unsaved session choices")
        .. (model.profileModified and " (modified)" or ""), true)
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
    if self.accountStatus and self.profileOverview then
        local ok, overview = pcall(self.profileOverview)
        if not ok or type(overview) ~= "table" then self.accountStatus:Set("Unavailable: account discovery could not be verified", true)
        else
            local rows = {}
            for index = 1, math.min(#overview.rows, 3) do
                local row = overview.rows[index]
                rows[#rows + 1] = row.account .. ": " .. (row.status ~= "Available" and row.status
                    or (tostring(row.profiles) .. " saved; autoload " .. (row.autoload or "Off") .. "; once " .. (row.once or "Off")))
            end
            if #overview.rows > 3 or overview.truncated then rows[#rows + 1] = "More accounts omitted from this compact view" end
            self.accountStatus:Set(#rows > 0 and table.concat(rows, "\n") or "No same-place saved profiles discovered", true)
        end
    end
    local names, autoload, reason, nextLoad = self.profileSummary()
    if reason then
        self.storageStatus:Set("Unavailable — " .. reason, true)
        self.autoloadStatus:Set("Unavailable", true)
        self.nextLoadStatus:Set("Unavailable", true)
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
    self.nextLoadStatus:Set(nextLoad or "Off", true)
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
        profileOverview = callbacks.profileOverview,
        profileStatus = sessionGroup:Status({ Text = "Staged profile", Default = "None" }),
        selectionStatus = sessionGroup:Status({ Text = "Current choices", Default = "0 selected" }),
        appliedStatus = sessionGroup:Status({ Text = "Current saved profile",
            Default = "Unsaved session choices" }),
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
        result.autoloadStatus = savedGroup:Status({ Text = "Autoload on each launch",
            Default = "Loading" })
        result.nextLoadStatus = savedGroup:Status({ Text = "Next launch only", Default = "Loading" })
        result.accountStatus = savedGroup:Status({ Text = "Account autoload overview", Default = "Loading" })
        result.syncStatus = savedGroup:Status({ Text = "Saving edits", Default = "Manual" })
        result.syncToggle = savedGroup:Toggle({ Text = "Save edits to active profile", Default = false,
            Save = false, FireOnStart = false, Reapply = false,
            Callback = function(value, _, origin)
                if not userOrigin(origin) then return end
                local ok, current = pcall(result.syncToggle.Get, result.syncToggle)
                if ok and current == value then
                    callbacks.command(value and "enableProfileSync" or "disableProfileSync")
                end
            end })
        savedGroup:Description({ Text = "Automatic saving is optional and applies to later edits of the active profile. Save existing unsaved choices first. Pause and Stop preserve the saved desired choices." })
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
                    local ok, current = pcall(result.savedSelection.Get, result.savedSelection)
                    if ok and current == name then result.profileName:Set(name, true) end
                end
            end,
        })
        button(savedGroup, "Save choices locally", "saveProfile")
        button(savedGroup, "Preview saved profile", "previewProfile")
        button(savedGroup, "Refresh saved profiles", "refreshProfiles")
        button(savedGroup, "Autoload this saved profile", "enableAutoload")
        button(savedGroup, "Disable autoload", "disableAutoload")
        button(savedGroup, "Use once on next launch", "nextLoadProfile")
        button(savedGroup, "Clear next launch choice", "clearNextLoad")
        result.renameName = savedGroup:Input({ Text = "Replacement profile name", Default = "",
            Save = false, FireOnStart = false, FireOnBlur = false, Reapply = false })
        savedGroup:Description({ Text = "Renaming preserves choices. Clear autoload and next-launch choices for that profile first; existing names are never overwritten by Rename." })
        button(savedGroup, "Rename saved profile", "renameProfile")
        savedGroup:Description({ Text = "To delete a saved profile, pause and preview that exact profile first. Current session choices stay available." })
        button(savedGroup, "Delete previewed profile", "deleteProfile")
    end
    if callbacks.profileTransfer then
        local transfer = section:Group({ Text = "Transfer choices", Open = false })
        transfer:Description({ Text = "Export copies only settings into this text field. Import replaces choices; omitted settings use defaults. Preview first; Apply is separate and pauses the session. No code is executed." })
        result.transferText = transfer:Input({ Text = "Settings JSON", Default = "",
            Save = false, FireOnStart = false, FireOnBlur = false, Reapply = false })
        button(transfer, "Export current choices", "exportProfile")
        button(transfer, "Preview imported choices", "importProfile")
        transfer:Description({ Text = "Legacy review shows original choices, mapped settings, updated defaults and unresolved intent. Copy this review to inspect it; editing review text does not change staged choices." })
        result.importReviewText = transfer:Input({ Text = "Import review JSON", Default = "",
            Save = false, FireOnStart = false, FireOnBlur = false, Reapply = false })
    else
        sessionGroup:Description({ Text = "Text import/export is unavailable without the settings JSON adapter." })
    end
    button(sessionGroup, "Stage current choices", "stage")
    button(sessionGroup, "Apply staged choices", "apply")
    button(sessionGroup, "Discard staged choices", "discard")
    result:RefreshStorage()
    return result
end

return ProfilesTab
