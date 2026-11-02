-- Saved CollectionTab deposit signature; describes but never invokes.
local CollectionCallPlan = {}

local function id(value)
    return type(value) == "string" and #value > 0
        and #value <= 120 and value:match("^[%w_]+$") ~= nil
end

local function integer(value)
    return type(value) == "number" and value == value
        and value >= 1 and value <= 10 and value % 1 == 0
end

function CollectionCallPlan.describe(proposal)
    local intent = type(proposal) == "table" and proposal.intent
    if proposal.feature == "collectionDonate"
        and type(intent) == "table"
        and intent.kind == "collectionDonate"
        and id(intent.itemId)
        and integer(intent.amount)
        and type(intent.catalogKey) == "string"
        and #intent.catalogKey > 0 then
        return { remote = "CollectionAction",
            method = "InvokeServer", arity = 3,
            args = { "deposit", intent.itemId, intent.amount },
            source = "saved CollectionTab ordinary deposit call" }, nil
    end
    return nil, "No reviewed Collection call contract"
end

return CollectionCallPlan
