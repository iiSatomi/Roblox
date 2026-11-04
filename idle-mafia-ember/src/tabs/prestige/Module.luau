-- Rank-specific preview and separately opted-in reset with current usage proof.
local PrestigeTab = {}
local Methods = {}
Methods.__index = Methods

local blocked = "Reset requires durable attempt ownership and native controller arbitration"

function PrestigeTab.BuildUI(section, feature, bind, numeric, resetAvailable)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "prestige" and feature.id == "prestige"
        and type(bind) == "function", "Invalid Prestige UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", "prestige.enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    local unavailable = resetAvailable ~= true and blocked or nil
    group:Description({ Text = unavailable or "Reset is not live-verified. Explicit reset consent and a persistent attempt limit are required." })
    group:Description({ Text = "A reset sets your current level to 1 and current EXP to 0. This cannot be undone." })
    numeric = numeric or {}
    local custom = group:Group({ Text = "Reset selection and limits", Open = false })
    for _, field in ipairs(feature.custom) do
        local key = "prestige.custom." .. field.id
        if field.type == "boolean" then
            bind(custom, "Toggle", key, { Text = field.label, Default = false,
                RevertOnClose = true, RevertTo = false })
        else
            assert(field.type == "number", "Invalid Prestige reset setting")
            numeric[key] = true
            bind(custom, "Input", key, { Text = field.label,
                Default = tostring(field.value), FireOnBlur = true })
        end
    end
    return { feature = feature, tabOwned = true,
        custom = custom,
        blockedReason = unavailable,
        status = group:Status({ Text = "Activity",
            Default = unavailable and ("Blocked — " .. unavailable) or "Off" }) }
end

function PrestigeTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.PrestigeState) == "table"
        and type(deps.PrestigeState.new) == "function"
        and type(deps.PrestigeState.read) == "function"
        and type(deps.PrestigeBlocked) == "table"
        and type(deps.PrestigeBlocked.propose) == "function"
        and type(deps.PrestigeBlocked.capture) == "function"
        and type(deps.PrestigeBlocked.evaluate) == "function",
        "Missing Prestige tab module")
    local state = deps.PrestigeState.new(
        deps.config, deps.fingerprint, deps.release)
    local reset
    if deps.PrestigeReset ~= nil then
        assert(type(deps.PrestigeReset) == "table"
            and type(deps.PrestigeReset.new) == "function", "Invalid Prestige reset module")
        reset = deps.PrestigeReset.new(state)
    end
    return setmetatable({ id = "prestige", state = state,
        reset = reset, blocked = deps.PrestigeBlocked, controller = deps.nativePrestigeController,
        controllerRead = type(deps.nativePrestigeController) == "table" and deps.nativePrestigeController.Read or nil,
        controllerCurrent = type(deps.nativePrestigeController) == "table" and deps.nativePrestigeController.Current or nil,
        nativePrestigeLease = deps.nativePrestigeLease, resetModule = deps.PrestigeReset, describeReset = type(deps.PrestigeReset) == "table" and deps.PrestigeReset.describe or nil }, Methods)
end

function Methods:Enrich(snapshot)
    if self.closed then return nil, "Prestige owner closed" end
    local result, why = self.state:Enrich(snapshot)
    self.latestSnapshot = result
    return result, why
end

function Methods:CanDispatch(proposal)
    local raw, source = self.latestSnapshot, self.controller
    if self.closed or not self.reset or type(raw) ~= "table" or type(proposal) ~= "table"
        or type(source) ~= "table" or type(self.controllerRead) ~= "function" or type(self.controllerCurrent) ~= "function"
        or source.Read ~= self.controllerRead or source.Current ~= self.controllerCurrent
        or type(self.describeReset) ~= "function" or self.resetModule.describe ~= self.describeReset then return false end
    for _, key in ipairs({"session", "account", "place", "release", "revision"}) do if proposal[key] ~= raw[key] then return false end end
    local call = self.describeReset(proposal)
    local intent = proposal.intent
    if not call or intent.catalogKey ~= self.state.key or proposal.actionKey ~= "prestige:" .. intent.rankBefore .. ":" .. intent.nextRank then return false end
    local currentOk, valid = pcall(self.controllerCurrent, source)
    if not currentOk or valid ~= true then return false end
    local ok, value = pcall(self.controllerRead, source)
    local afterOk, afterValid = pcall(self.controllerCurrent, source)
    return ok and type(value) == "table" and afterOk and afterValid == true
        and source.Read == self.controllerRead and source.Current == self.controllerCurrent
        and value.controllersClear == true and value.ready == true and value.rank == intent.rankBefore
        and value.level == intent.levelBefore and value.xp == intent.xpBefore
end

function Methods:Close()
    self.closed, self.latestSnapshot = true, nil
    if type(self.controller) == "table" and type(self.controller.Close) == "function" then pcall(self.controller.Close, self.controller) end
    if self.nativePrestigeLease ~= self.controller and type(self.nativePrestigeLease) == "table"
        and type(self.nativePrestigeLease.Close) == "function" then pcall(self.nativePrestigeLease.Close, self.nativePrestigeLease) end
end

function Methods:Descriptors()
    return { { id = "prestige", reader = self.state,
        planner = self.reset or self.blocked, evidence = self.reset or self.blocked,
        canDispatch = self.reset and function(proposal) return self:CanDispatch(proposal) end or nil,
        recoverSaved = self.reset and self.reset.recoverSaved or nil } }
end

function Methods:Preview(snapshot, context)
    return self.state.read(snapshot, context)
end

return PrestigeTab
