-- Separate Family controls never acquire shared spending authority here.
local FamilyBlocked = {}

function FamilyBlocked.propose()
    return nil, "Shared Family spending requires separate consent and custody proof"
end

function FamilyBlocked.capture()
    return nil, "Family contribution send is blocked"
end

function FamilyBlocked.evaluate()
    return "pending"
end

return FamilyBlocked
