-- Fallback until a current native offer and earned-custody source is installed.
local EventShopBlocked = {}

function EventShopBlocked.read()
    return nil, "Current Event Shop offers and medal custody are not connected"
end

function EventShopBlocked.propose()
    return nil, "Current Event Shop offers and earned medal origin are not connected"
end

function EventShopBlocked.capture()
    return nil, "Event Shop send is blocked"
end

function EventShopBlocked.evaluate()
    return "pending"
end

return EventShopBlocked
