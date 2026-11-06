-- Reviewed one-member station and selected residence request calls.
local TerritoryCallPlan = {}
function TerritoryCallPlan.describe(proposal)
    local intent = type(proposal) == "table" and proposal.intent
    if type(intent) == "table" and proposal.feature == "residency"
        and intent.kind == "residencyRequest" and type(intent.districtId) == "string"
        and #intent.districtId > 0 and #intent.districtId <= 120
        and type(intent.previousDistrict) == "string" and #intent.previousDistrict <= 120
        and type(intent.allowReplace) == "boolean" and type(intent.allowRequests) == "boolean"
        and type(intent.rent) == "number" and intent.rent == intent.rent
        and type(intent.maxRentPct) == "number" and intent.maxRentPct >= 0
        and intent.maxRentPct <= 10 and intent.rent >= 0 and intent.rent <= intent.maxRentPct then
        return { remote = "ResidencyAction", method = "InvokeServer", arity = 3,
            args = { "request", intent.districtId }, source = "saved ResidencyPanel request call" }, nil
    end
    if type(intent) == "table" and proposal.feature == "station"
        and intent.kind == "territoryStation" and type(intent.districtId) == "string"
        and #intent.districtId > 0 and #intent.districtId <= 120
        and type(intent.memberSlot) == "number" and intent.memberSlot % 1 == 0
        and intent.memberSlot >= 2 and intent.memberSlot <= 46
        and type(intent.memberKey) == "string" and #intent.memberKey > 0
        and #intent.memberKey <= 131 then
        return { remote = "TerritoryAction", method = "InvokeServer", arity = 4,
            args = { "station", intent.districtId, intent.memberSlot },
            source = "saved TerritoryTab individual station call" }, nil
    end
    return nil, "Unreviewed Territory mutation signature"
end
function TerritoryCallPlan.withRecall(recall)
    assert(type(recall) == "table" and type(recall.describe) == "function", "Missing reviewed Recall call plan")
    return {describe = function(proposal)
        if type(proposal) == "table" and type(proposal.intent) == "table"
            and proposal.intent.kind == "territoryRecall" then return recall.describe(proposal) end
        return TerritoryCallPlan.describe(proposal)
    end}
end
return TerritoryCallPlan
