-- Separate personal contribution lanes. UI labels do not gate native execution.
-- Contributions remain default-off with independent saved resource budgets.
-- Multi-perk rotation tracks only exact confirmed outcomes in this tab session.
local FamilyTab = {}
local Methods = {}
Methods.__index = Methods

local known = {familyCash = true, familyStamina = true, familyGold = true}

function FamilyTab.BuildUI(section, feature, bind, numeric)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "family" and known[feature.id]
        and type(bind) == "function", "Invalid Family UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    group:Description({ Text = "Requires fresh Family info and saved limits. Budget usage survives reloading." })
    numeric = numeric or {}
    local custom = group:Group({ Text = "Contribution limits", Open = false })
    for _, field in ipairs(feature.custom) do
        local key = feature.id .. ".custom." .. field.id
        if field.type == "number" or field.type == "text" then
            if field.type == "number" then numeric[key] = true end
            bind(custom, "Input", key, { Text = field.label,
                Default = tostring(field.value), FireOnBlur = true, Description = field.description })
        elseif field.type == "boolean" then
            bind(custom, "Toggle", key, {Text = field.label, Default = field.value,
                RevertOnClose = true, RevertTo = false})
        else
            assert(field.type == "select", "Invalid Family preference")
            bind(custom, "Dropdown", key, { Text = field.label,
                Default = field.value, Options = field.options })
        end
    end
    return { feature = feature, tabOwned = true,
        custom = custom,
        status = group:Status({ Text = "Activity",
            Default = "Off" }) }
end

function FamilyTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.FamilyQuery) == "table"
        and type(deps.FamilyQuery.new) == "function"
        and type(deps.FamilyState) == "table"
        and type(deps.FamilyState.read) == "function"
        and type(deps.FamilyBlocked) == "table"
        and type(deps.FamilyBlocked.propose) == "function"
        and type(deps.FamilyBlocked.capture) == "function"
        and type(deps.FamilyBlocked.evaluate) == "function",
        "Missing Family info module")
    local state, evidence
    if type(deps.FamilyContributionState) == "table"
        and type(deps.FamilyContributions) == "table"
        and type(deps.FamilyContributionEvidence) == "table"
        and type(deps.config) == "table" and type(deps.config.FAMILY) == "table" then
        state = deps.FamilyContributionState.new(deps.config, deps.fingerprint, deps.release, deps.playerInfoSource)
        evidence = deps.FamilyContributionEvidence.new(deps.FamilyContributionState)
    end
    return setmetatable({ id = "family", ownedProofs = {"familyActorProof"}, deps = deps, state = state, closed = false,
        infoQuery = deps.FamilyQuery.new(state),
        evidence = evidence }, Methods)
end

function Methods:ReadSources(reader)
    if self.closed or not self.state or type(reader) ~= "table"
        or type(reader.AttachFamilyContribution) ~= "function" then return {} end
    return {{id = "familyInfo", interval = 5,
        confirmFeatures = {familyCash = true, familyGold = true, familyStamina = true},
        enabled = function(settings, active)
            for _, feature in ipairs({"familyCash", "familyGold", "familyStamina"}) do
                if (type(active) == "table" and active.feature == feature)
                    or (type(settings[feature]) == "table" and settings[feature].enabled == true) then return true end
            end
            return false
        end,
        prepare = function(snapshot)
            if self.closed then return nil, "Family tab closed" end
            return self.infoQuery:Prepare(snapshot)
        end,
        accept = function(snapshot, request, reply)
            return self.infoQuery:Stage(snapshot, request, reply)
        end,
        commit = function(staged) return not self.closed and reader:AttachFamilyContribution(staged) end,
    }}
end

function Methods:Close()
    if self.closed then return end
    self.closed = true
    self.latestSnapshot = nil
    self.lastStaminaPerk, self.rotationFamily = nil, nil
    self.infoQuery:Close()
end

function Methods:NewInfoQuery()
    return self.deps.FamilyQuery.new(self.state)
end

function Methods:Enrich(snapshot)
    self.latestSnapshot = snapshot
    local familyId = type(snapshot.native) == "table" and type(snapshot.native.family) == "table" and snapshot.native.family.id
    if familyId ~= self.rotationFamily then
        self.rotationFamily, self.lastStaminaPerk = familyId, nil
    end
    if not self.state then return snapshot, nil end
    local enriched = self.state:Enrich(snapshot)
    return enriched or snapshot, nil
end

function Methods:Descriptors()
    local d = self.deps
    if self.state then
        return {
            { id = "familyCash", reader = self.state,
                planner = d.FamilyContributions.cash, evidence = self.evidence, recoverSaved = self.evidence.recoverSaved,
                canDispatch = function(proposal) return not self.closed and self.evidence.canDispatch(proposal, self.latestSnapshot and self.state:Enrich(self.latestSnapshot)) end },
            { id = "familyStamina", reader = self.state,
                planner = {propose = function(view, settings, reservations)
                    if self.closed then return nil, "Family tab closed" end
                    local current = {}
                    for key, value in pairs(view) do current[key] = value end
                    current.lastStaminaPerk = view.familyId == self.rotationFamily and self.lastStaminaPerk or nil
                    return d.FamilyContributions.stamina.propose(current, settings, reservations)
                end}, evidence = self.evidence, recoverSaved = self.evidence.recoverSaved,
                recordOutcome = function(data, after, outcome)
                    if self.closed or outcome ~= "confirmed"
                        or self.evidence.recoverSaved(data, after) ~= "confirmed" then
                        return false, "Exact confirmed Family contribution required"
                    end
                    -- Session-only rotation; exact saved receipts may seed a fresh owner.
                    self.rotationFamily = data.proposal.intent.familyId
                    self.lastStaminaPerk = data.proposal.intent.perkId
                    return true
                end,
                canDispatch = function(proposal) return not self.closed and self.evidence.canDispatch(proposal, self.latestSnapshot and self.state:Enrich(self.latestSnapshot)) end },
            { id = "familyGold", reader = self.state,
                planner = d.FamilyContributions.gold, evidence = self.evidence, recoverSaved = self.evidence.recoverSaved,
                canDispatch = function(proposal) return not self.closed and self.evidence.canDispatch(proposal, self.latestSnapshot and self.state:Enrich(self.latestSnapshot)) end },
        }
    end
    return {
        { id = "familyCash", reader = d.FamilyState,
            planner = d.FamilyBlocked, evidence = d.FamilyBlocked },
        { id = "familyStamina", reader = d.FamilyState,
            planner = d.FamilyBlocked, evidence = d.FamilyBlocked },
        { id = "familyGold", reader = d.FamilyState,
            planner = d.FamilyBlocked, evidence = d.FamilyBlocked },
    }
end

return FamilyTab
