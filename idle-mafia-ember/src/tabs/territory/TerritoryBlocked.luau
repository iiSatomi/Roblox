-- Map viewing is separate. No station or residency mutation is authorized here.
local TerritoryBlocked = {}

function TerritoryBlocked.propose()
    return nil, "Territory mutation requires current member, capacity, rent and rollback proof"
end

function TerritoryBlocked.capture()
    return nil, "Territory mutation send is blocked"
end

function TerritoryBlocked.evaluate()
    return "pending"
end

return TerritoryBlocked
