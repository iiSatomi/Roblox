-- Claims, completion bonuses and goal inspection remain separate.
local ContractsTab = {}
local Methods = {}
Methods.__index = Methods
local known = { contracts = true, bonuses = true,
    autoContracts = true }

function ContractsTab.BuildUI(section, feature, bind)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "contracts" and known[feature.id]
        and type(bind) == "function", "Invalid Contracts UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity for the prototype.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    local reason = feature.id == "autoContracts"
        and "Cross-tab borrowing awaits shared opt-in and progress proof" or nil
    if reason then group:Description({ Text = reason }) end
    return { feature = feature, tabOwned = true,
        blockedReason = reason,
        status = group:Status({ Text = "Activity",
            Default = reason and "Blocked — " .. reason
                or "Off — UI only" }) }
end

function ContractsTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.ContractEntriesState) == "table"
        and type(deps.ContractEntriesState.read) == "function"
        and type(deps.ContractEntries) == "table"
        and type(deps.ContractEntries.propose) == "function"
        and type(deps.ContractEntriesEvidence) == "table"
        and type(deps.ContractEntriesEvidence.capture) == "function"
        and type(deps.ContractEntriesEvidence.evaluate) == "function"
        and type(deps.ContractBonusesState) == "table"
        and type(deps.ContractBonusesState.read) == "function"
        and type(deps.ContractBonuses) == "table"
        and type(deps.ContractBonuses.propose) == "function"
        and type(deps.ContractBonusesEvidence) == "table"
        and type(deps.ContractBonusesEvidence.capture) == "function"
        and type(deps.ContractBonusesEvidence.evaluate) == "function"
        and type(deps.ContractGoalState) == "table"
        and type(deps.ContractGoalState.read) == "function"
        and type(deps.ContractGoalBlocked) == "table"
        and type(deps.ContractGoalBlocked.propose) == "function"
        and type(deps.ContractGoalBlocked.capture) == "function"
        and type(deps.ContractGoalBlocked.evaluate) == "function"
        and type(deps.ContractCashQuote) == "table"
        and type(deps.ContractCashQuote.read) == "function"
        and type(deps.NativeContractCatalog) == "table"
        and type(deps.NativeContractCatalog.new) == "function",
        "Missing Contracts tab modules")
    local catalog = deps.NativeContractCatalog.new(deps.config,
        deps.fingerprint, deps.release)
    return setmetatable({ id = "contracts", deps = deps,
        catalog = catalog }, Methods)
end

function Methods:ReadCashQuote(raw, context)
    return self.deps.ContractCashQuote.read(raw, context)
end

function Methods:Enrich(snapshot)
    return self.catalog:Enrich(snapshot)
end

function Methods:Descriptors()
    local d = self.deps
    return {
        { id = "contracts", reader = d.ContractEntriesState,
            planner = d.ContractEntries,
            evidence = d.ContractEntriesEvidence },
        { id = "bonuses", reader = d.ContractBonusesState,
            planner = d.ContractBonuses,
            evidence = d.ContractBonusesEvidence },
        { id = "autoContracts", reader = d.ContractGoalState,
            planner = d.ContractGoalBlocked,
            evidence = d.ContractGoalBlocked },
    }
end

return ContractsTab
