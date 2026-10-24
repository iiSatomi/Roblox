-- Explicit non-sending descriptors until the read scheduler and trade custody are wired.
local MarketBlocked = {}

local function descriptor(reason)
    return {
        read = function() return nil, reason end,
        propose = function() return nil, reason end,
        capture = function() return nil, reason end,
        evaluate = function() return "pending" end,
    }
end

MarketBlocked.watch = descriptor(
    "Market research requires the bounded current-client query scheduler")
MarketBlocked.trade = descriptor(
    "Market trade requires separate Gold or inventory custody consent and proof")

return MarketBlocked
