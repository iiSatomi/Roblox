-- Local relations editor. Sub-page controls never enable hostile actions.
local Tab, Methods = {}, {}; Methods.__index = Methods
local function ids(value)
    local list, seen = {}, {}
    for raw in (value or ""):gmatch("[^,]+") do
        local id = raw:match("^%s*(.-)%s*$")
        if id ~= "" and not seen[id] then list[#list + 1] = id;seen[id] = true end
    end
    return list, seen
end
function Tab.new(section, bind, change, alive, userOrigin)
    local self = setmetatable({panels = {}, switches = {}, saved = {}, add = {}, remove = {},
        labels = {}, names = {}, values = {}, lastLists = {}, active = "allies"}, Methods)
    local function action(container, text, fn)
        return container:Button({Text = text, ButtonText = text, Save = false, FireOnStart = false,
            Callback = function(_, _, origin) if alive() and userOrigin(origin) then fn() end end})
    end
    section:Description({Text = "Local targeting rules, not an in-game treaty. Allies always win conflicts. Combat/Scout uses fresh target membership and checks choices again before sending. Sabotage and war actions remain unavailable until their own contracts are implemented."})
    local nav = section:Group({Text = "Sub-tabs", Open = true})
    for _, entry in ipairs({{"allies", "Alliances"}, {"enemies", "Enemies"}}) do
        local key = entry[1]
        self.switches[key] = action(nav, entry[2], function() self:Select(key) end)
    end
    local directory = section:Group({Text = "Find a Family", Open = true})
    bind(directory, "Input", "alliance.query", {Text = "Family name to search", Default = "", FireOnBlur = true})
    bind(directory, "Toggle", "alliance.browse", {Text = "Load Family directory", Default = false, RevertOnClose = true, RevertTo = false})
    directory:Description({Text = "Read-only search while the hub is running; at most once per minute through the shared request lane. Results are a partial native directory. Turn loading off when finished. Saved Family IDs remain protected even when absent from these results."})
    self.status = directory:Status({Text = "Directory", Default = "Unavailable — enable loading and resume"})
    self.picker = directory:Dropdown({Text = "Family", Options = {}, Save = false, FireOnStart = false})
    for _, entry in ipairs({{"allies", "Alliances"}, {"enemies", "Enemies"}}) do
        local key, title = entry[1], entry[2]
        local panel = section:Group({Text = title, Open = true});self.panels[key] = panel
        panel:Description({Text = key == "allies" and "Never automatically mug or scout these Families. Your own Family and friends retain their separate native protections."
            or "Choose enemy Families below. Target mode changes priority or eligibility only; it never enables Combat, spends beyond your limits, or overrides ally protection."})
        if key == "enemies" then
            bind(panel, "Dropdown", "alliance.mode", {Text = "Enemy target mode", Options = {"Off", "Prefer enemies", "Enemies only"}, Default = "Off"})
        end
        self.add[key] = action(panel, "Add selected Family to " .. title, function()
            local id = self.labels[self.picker:Get()]
            if not id then return end
            local list, seen = ids(self.values["alliance." .. key])
            if not seen[id] and #list < 64 then list[#list + 1] = id; change("alliance." .. key, table.concat(list, ",")) end
        end)
        self.saved[key] = panel:Dropdown({Text = "Saved " .. title, Options = {}, Save = false, FireOnStart = false})
        self.remove[key] = action(panel, "Remove selected " .. (key == "allies" and "ally" or "enemy"), function()
            local selected = self.saved[key]:Get();local remove = self.savedIds[key] and self.savedIds[key][selected]
            if not remove then return end
            local kept = {};for _, id in ipairs(ids(self.values["alliance." .. key])) do if id ~= remove then kept[#kept + 1] = id end end
            change("alliance." .. key, table.concat(kept, ","))
        end)
        bind(panel, "Input", "alliance." .. key, {Text = title .. " Family IDs (comma separated, maximum 64)", Default = "", FireOnBlur = true})
    end
    self.savedIds = {};self:Select("allies")
    return self
end
function Methods:Select(key)
    self.active = key
    for name, panel in pairs(self.panels) do panel:SetVisible(name == key) end
end
function Methods:Render(model)
    self.values = model.values
    local view = model.automationRuntime and model.automationRuntime.familyDirectory
    local valid = type(view) == "table" and view.query == model.values["alliance.query"] and type(view.rows) == "table"
    local options, labels, names = {}, {}, {}
    for _, row in ipairs(valid and view.rows or {}) do
        local label = row.name .. " [" .. row.id .. "]"
        options[#options + 1] = label;labels[label] = row.id;names[row.id] = row.name
    end
    local signature = table.concat(options, "\n")
    if self.directorySignature ~= signature then
        self.directorySignature = signature; self.picker:SetOptions(options, true)
    end
    self.labels, self.names = labels, names
    local reason = model.automationRuntime and model.automationRuntime.reads
    reason = type(reason) == "table" and reason.reasons and reason.reasons.allianceDirectory
    local text = not valid and "Unavailable — enable loading and resume; search waits for the shared read lane"
        or ((view.ready and "Last returned list: " or "Partial native list: ") .. tostring(#options) .. " Families")
    if reason then text = text .. "; " .. tostring(reason) end
    if text ~= self.lastStatus then self.status:Set(text, true);self.lastStatus = text end
    for _, key in ipairs({"allies", "enemies"}) do
        local saved, map = {}, {}
        for _, id in ipairs(ids(model.values["alliance." .. key])) do
            local label = names[id] and (names[id] .. " [" .. id .. "]") or id
            saved[#saved + 1] = label;map[label] = id
        end
        local signature = table.concat(saved, "\n")
        if self.lastLists[key] ~= signature then self.saved[key]:SetOptions(saved, true);self.lastLists[key] = signature end
        self.savedIds[key] = map
    end
    return true
end
return Tab
