-- Banking and purpose-specific funding remain independent controls.
local MoneyTab = {}
local Methods = {}
Methods.__index = Methods

local known = { bank = true, withdraw = true }

function MoneyTab.BuildUI(section, feature, bind, numeric)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "money" and known[feature.id]
        and type(bind) == "function" and type(numeric) == "table"
        and type(feature.policies) == "table"
        and type(feature.custom) == "table",
        "Invalid Money UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    if feature.limits then group:Description({ Text = feature.limits }) end
    local row = { feature = feature, tabOwned = true,
        status = group:Status({ Text = "Activity",
            Default = "Off — UI only" }) }
    row.custom = group:Group({ Text = "Cash limits", Open = false })
    for _, field in ipairs(feature.custom) do
        assert(field.type == "number", "Invalid Money custom control")
        local key = feature.id .. ".custom." .. field.id
        numeric[key] = true
        bind(row.custom, "Input", key, {
            Text = field.label, Default = tostring(field.value),
            FireOnBlur = true,
        })
    end
    return row
end

function MoneyTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.BankState) == "table"
        and type(deps.BankState.read) == "function"
        and type(deps.BankDeposits) == "table"
        and type(deps.BankDeposits.propose) == "function"
        and type(deps.BankDepositsEvidence) == "table"
        and type(deps.BankDepositsEvidence.capture) == "function"
        and type(deps.BankDepositsEvidence.evaluate) == "function"
        and type(deps.WithdrawalState) == "table"
        and type(deps.WithdrawalState.read) == "function"
        and type(deps.PurposeWithdrawals) == "table"
        and type(deps.PurposeWithdrawals.propose) == "function"
        and type(deps.PurposeWithdrawalsEvidence) == "table"
        and type(deps.PurposeWithdrawalsEvidence.capture) == "function"
        and type(deps.PurposeWithdrawalsEvidence.evaluate) == "function"
        and type(deps.NativeBankCatalog) == "table"
        and type(deps.NativeBankCatalog.new) == "function",
        "Missing Money tab modules")
    local fee = deps.NativeBankCatalog.new(
        deps.config, deps.fingerprint, deps.release)
    return setmetatable({ id = "money", deps = deps,
        fee = fee }, Methods)
end

function Methods:Enrich(snapshot)
    return self.fee:Enrich(snapshot)
end

function Methods:Descriptors()
    local d = self.deps
    return {
        { id = "bank", reader = d.BankState,
            planner = d.BankDeposits, evidence = d.BankDepositsEvidence },
        { id = "withdraw", reader = d.WithdrawalState,
            planner = d.PurposeWithdrawals,
            evidence = d.PurposeWithdrawalsEvidence },
    }
end

return MoneyTab
