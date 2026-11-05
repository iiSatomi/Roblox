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
    row.custom = group:Group({ Text = feature.id == "withdraw"
        and "Funding purposes and cash limits" or "Cash limits", Open = false })
    for _, field in ipairs(feature.custom) do
        local key = feature.id .. ".custom." .. field.id
        if field.type == "boolean" then
            bind(row.custom, "Toggle", key, { Text = field.label, Default = field.value })
        else
            assert(field.type == "number", "Invalid Money custom control")
            numeric[key] = true
            bind(row.custom, "Input", key, {
                Text = field.label, Default = tostring(field.value), FireOnBlur = true,
            })
        end
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
    return setmetatable({ id = "money", deps = deps, fee = fee,
        nativeState = deps.nativeState,
        nativeLatest = type(deps.nativeState) == "table" and deps.nativeState.latest or nil,
        closed = false }, Methods)
end

function Methods:Enrich(snapshot)
    if self.closed then return nil, "Money tab closed" end
    local enriched, reason = self.fee:Enrich(snapshot)
    self.latestSnapshot = enriched
    return enriched, reason
end

function Methods:CanDispatch(proposal)
    if self.closed or type(proposal) ~= "table" then return false end
    -- Offline integrations supply their own observation seam. In the current
    -- client, projected/native changes are a veto only, never effect evidence.
    if self.nativeState == nil then return true end
    local state, latest, expected = self.nativeState, self.nativeLatest, self.latestSnapshot
    if self.deps.nativeState ~= state or type(latest) ~= "function" or state.latest ~= latest
        or type(expected) ~= "table" or type(expected.native) ~= "table" then return false end
    for _, key in ipairs({"session", "account", "place", "release", "revision"}) do
        if proposal[key] ~= expected[key] then return false end
    end
    local ok, native = pcall(latest)
    if not ok or type(native) ~= "table" or self.closed or self.latestSnapshot ~= expected
        or self.deps.nativeState ~= state or state.latest ~= latest
        or type(native.userId) ~= "number" or native.userId < 1 or native.userId > 9007199254740991
        or native.userId % 1 ~= 0 or native.userId ~= expected.native.userId
        or native.cash ~= expected.native.cash or native.banked ~= expected.native.banked
        or type(proposal.intent) ~= "table" then return false end
    local intent = proposal.intent
    if proposal.feature == "bank" then
        return type(native.derived) == "table" and native.derived.noBankFees == intent.noFee
    end
    return proposal.feature == "withdraw" and type(intent.requiredCash) == "number"
        and native.cash < intent.requiredCash
        and math.ceil(intent.requiredCash - native.cash) == intent.amount
        and native.banked >= intent.amount
end

function Methods:Close()
    if self.closed then return end
    self.closed = true
    self.latestSnapshot, self.nativeState, self.nativeLatest = nil, nil, nil
end

function Methods:Descriptors()
    local d = self.deps
    return {
        { id = "bank", reader = d.BankState,
            planner = d.BankDeposits, evidence = d.BankDepositsEvidence,
            recoverSaved = d.BankDepositsEvidence.recoverSaved,
            canDispatch = function(proposal) return self:CanDispatch(proposal) end },
        { id = "withdraw", reader = d.WithdrawalState,
            planner = d.PurposeWithdrawals,
            evidence = d.PurposeWithdrawalsEvidence,
            recoverSaved = d.PurposeWithdrawalsEvidence.recoverSaved,
            canDispatch = function(proposal) return self:CanDispatch(proposal) end },
    }
end

return MoneyTab
