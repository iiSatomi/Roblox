-- Cross-tab borrowing stays inert until the final shared coordinator exists.
local ContractGoalBlocked = {}

function ContractGoalBlocked.propose()
    return nil, "Contract goal borrowing requires shared opt-in and action-progress arbitration"
end

function ContractGoalBlocked.capture()
    return nil, "Contract goal controller does not send a remote"
end

function ContractGoalBlocked.evaluate()
    return "pending"
end

return ContractGoalBlocked
