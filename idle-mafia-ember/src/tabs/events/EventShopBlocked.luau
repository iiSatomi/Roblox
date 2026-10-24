-- 0.26.530 save omits EventShopTab and EventShop definitions.
local EventShopBlocked = {}

function EventShopBlocked.read()
    return nil, "Current Event Shop offers, medal custody and native call unavailable"
end

function EventShopBlocked.propose()
    return nil, "Event Shop buying is blocked pending source and current quote"
end

function EventShopBlocked.capture()
    return nil, "Event Shop send is blocked"
end

function EventShopBlocked.evaluate()
    return "pending"
end

return EventShopBlocked
