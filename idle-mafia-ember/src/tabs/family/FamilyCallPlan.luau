-- Saved FamilyTab only: donate(amount,nil,nil), donategold(amount,nil,nil),
-- contribute(perk,1-or-5,nil). No vault upgrades, withdrawals or purchases.
local FamilyCallPlan = {}
local tracks = { enforcers = true, guardians = true, hustlers = true,
    medics = true, runners = true, bagmen = true, insurance = true,
    veterans = true, demolition = true, bosshunters = true }

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

function FamilyCallPlan.describe(proposal)
    local intent = type(proposal) == "table" and proposal.intent
    if type(intent) ~= "table" or intent.kind ~= "familyContribution"
        or not integer(intent.actorId, 1, 9007199254740991)
        or not integer(intent.ledgerBefore, 0, 9007199254740991)
        or not integer(intent.amount, 1, 1000000000000000) then
        return nil, "Invalid personal Family contribution"
    end
    local args
    if proposal.feature == "familyCash" and intent.resource == "cash" then
        args = { "donate", intent.amount }
    elseif proposal.feature == "familyGold" and intent.resource == "gold_bar" then
        args = { "donategold", intent.amount }
    elseif proposal.feature == "familyStamina" and intent.resource == "stamina"
        and tracks[intent.perkId] == true
        and (intent.amount == 1 or intent.amount == 5) then
        args = { "contribute", intent.perkId, intent.amount }
    end
    if not args then return nil, "Unreviewed Family contribution signature" end
    return { remote = "FamilyAction", method = "InvokeServer", arity = 4,
        args = args, source = "saved FamilyTab personal contribution" }, nil
end

return FamilyCallPlan
