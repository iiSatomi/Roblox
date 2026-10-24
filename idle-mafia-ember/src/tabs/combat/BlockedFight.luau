-- Separate player and war permissions remain inert until their contracts are proven.
local BlockedFight = {}

function BlockedFight.new(feature)
    assert(feature == "combat" or feature == "warCombat",
        "Unknown blocked fight")
    local reason = feature == "combat"
        and "Player attack permission and outcome contract unverified"
        or "War target identity, permission and outcome contract unverified"
    return {
        read = function() return nil, reason end,
        propose = function(_, settings)
            if type(settings) ~= "table" or settings.enabled ~= true then
                return nil, "Fight disabled"
            end
            return nil, reason
        end,
        capture = function() return nil, reason end,
        evaluate = function() return "pending" end,
    }
end

return BlockedFight
