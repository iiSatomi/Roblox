-- Prestige mutates progression; keep this descriptor observable but inert.
local PrestigeBlocked = {}

function PrestigeBlocked.propose()
    return nil, "Prestige resets level and EXP; explicit reset consent and live evidence required"
end

function PrestigeBlocked.capture()
    return nil, "Automatic Prestige reset is blocked"
end

function PrestigeBlocked.evaluate()
    return "pending"
end

return PrestigeBlocked
