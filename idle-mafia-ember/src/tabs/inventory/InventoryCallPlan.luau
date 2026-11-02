-- Saved InventoryTab signatures; this module describes and never invokes.
local InventoryCallPlan = {}

local function id(value)
    return type(value) == "string" and #value > 0
        and #value <= 120 and value:match("^[%w_]+$") ~= nil
end

local function key(value)
    return type(value) == "string" and #value > 0 and #value <= 120
end

local function integer(value, low, high)
    return type(value) == "number" and value == value
        and value >= low and value <= high and value % 1 == 0
end

function InventoryCallPlan.describe(proposal)
    local intent = type(proposal) == "table" and proposal.intent
    if type(intent) ~= "table" then
        return nil, "Missing Inventory intent"
    end
    if proposal.feature == "cosmetics" and intent.kind == "cosmetics"
        and (intent.cosmeticKind == "background"
            or intent.cosmeticKind == "border")
        and id(intent.itemId) and key(intent.sourceKey) then
        return { remote = intent.cosmeticKind == "background"
                and "EquipBackground" or "EquipBorder",
            method = "InvokeServer", arity = 1,
            args = { intent.itemId },
            source = "saved InventoryTab cosmetic equip call" }, nil
    end
    if proposal.feature == "chests" and intent.kind == "chests"
        and id(intent.itemId) and integer(intent.amount, 1, 10)
        and type(intent.luck) == "number"
        and intent.luck == intent.luck
        and intent.luck >= 0 and intent.luck <= 10
        and key(intent.catalogKey) then
        return { remote = "OpenCrate", method = "InvokeServer",
            arity = 4, args = { intent.itemId, false,
                intent.amount, intent.luck },
            source = "saved InventoryTab owned crate open call" }, nil
    end
    if proposal.feature == "restoratives"
        and intent.kind == "restoratives"
        and id(intent.itemId)
        and type(intent.fromBound) == "boolean"
        and integer(intent.sequence, 0, 2147483647)
        and key(intent.catalogKey) then
        return { remote = "UseConsumable",
            method = "InvokeServer", arity = 3,
            args = { intent.itemId, intent.fromBound,
                intent.sequence },
            source = "saved InventoryTab player consumable call" }, nil
    end
    return nil, "No reviewed Inventory call contract"
end

return InventoryCallPlan
