-- Jobs tab entry. Shared engine code stays outside the tab.
local JobsTab = {}
local Methods = {}
Methods.__index = Methods

function JobsTab.BuildUI(section, feature, bind, active, numeric)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.id == "jobs" and feature.page == "jobs"
        and type(bind) == "function" and type(active) == "function" and type(numeric) == "table"
        and type(feature.custom) == "table" and #feature.custom == 8
        and feature.custom[1].id == "selectedJobId"
        and feature.custom[1].type == "select",
        "Invalid Jobs UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", "jobs.enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    bind(group, "Dropdown", "jobs.policy", {
        Text = "Goal", Options = feature.policies,
        Default = feature.policies[1],
    })
    local city = feature.custom[7]
    assert(city.id == "city" and city.type == "select", "Missing Job city control")
    bind(group, "Dropdown", "jobs.custom.city", { Text = city.label, Options = city.options, Default = city.value })
    local chosen = group:Group({ Text = "Selected Job", Open = false })
    local field = feature.custom[1]
    local selected = bind(chosen, "Dropdown", "jobs.custom.selectedJobId", {
        Text = field.label, Options = field.options, Default = field.value,
    })
    chosen:Input({ Text = "Find Job", Placeholder = "Name or ID; press Enter",
        Default = "", Save = false, FireOnStart = false,
        Reapply = false, Callback = function(query, _, origin)
            if not active() then return end
            if origin and (origin.initial or origin.restored
                or origin.reapplied or origin.reverted) then return end
            if type(query) ~= "string" then return end
            local needle = string.lower(query)
            local current = selected:Get()
            local options = {}
            for _, id in ipairs(field.options) do
                local label = field.searchLabels and field.searchLabels[id] or ""
                if needle == "" or id == current
                    or string.find(string.lower(id), needle, 1, true)
                    or string.find(string.lower(label), needle, 1, true) then
                    options[#options + 1] = id
                end
            end
            selected:SetOptions(options, true)
        end })
    local bounds = group:Group({ Text = "Optional Job bounds", Open = false })
    bounds:Description({ Text = "Bounds are inclusive. Energy limits use the current native cost after mastery discounts. Inverted bounds wait for correction." })
    for index = 2, 6 do
        local limit = feature.custom[index]
        local key = "jobs.custom." .. limit.id
        if limit.type == "boolean" then
            bind(bounds, "Toggle", key, { Text = limit.label, Default = limit.value })
        else
            assert(limit.type == "number", "Unsupported Job bound control")
            numeric[key] = true
            bind(bounds, "Input", key, { Text = limit.label, Default = tostring(limit.value), FireOnBlur = true })
        end
    end
    local mastery = feature.custom[8]
    assert(mastery.id == "masteryTarget" and mastery.type == "select", "Missing Mastery target control")
    local target = group:Group({ Text = "Mastery target", Open = false })
    target:Description({ Text = "Used only for the Mastery goal. Named targets follow the native rule names; missing or ambiguous names hold this goal." })
    bind(target, "Dropdown", "jobs.custom.masteryTarget", { Text = mastery.label, Options = mastery.options, Default = mastery.value })
    if feature.limits then group:Description({ Text = feature.limits }) end
    return { feature = feature, tabOwned = true, custom = chosen, bounds = bounds,
        customPolicy = "Selected job",
        status = group:Status({ Text = "Activity", Default = "Off — UI only" }) }
end

function JobsTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.NativeJobCatalog) == "table"
        and type(deps.NativeJobCatalog.new) == "function"
        and type(deps.JobsState) == "table"
        and type(deps.JobsState.read) == "function"
        and type(deps.Jobs) == "table"
        and type(deps.Jobs.propose) == "function"
        and type(deps.JobsEvidence) == "table"
        and type(deps.JobsEvidence.capture) == "function"
        and type(deps.JobsEvidence.evaluate) == "function",
        "Missing Jobs tab modules")
    local catalog = deps.NativeJobCatalog.new(deps.gameData,
        deps.config, deps.fingerprint, deps.release)
    return setmetatable({ id = "jobs", catalog = catalog,
        reader = deps.JobsState, planner = deps.Jobs,
        evidence = deps.JobsEvidence }, Methods)
end

function Methods:Descriptor()
    return { id = "jobs", reader = self.reader,
        planner = self.planner, evidence = self.evidence }
end

function Methods:Descriptors()
    return { self:Descriptor() }
end

function Methods:Enrich(snapshot)
    return self.catalog:Enrich(snapshot)
end

return JobsTab
