-- A visible result is not an addressable, sequence-owned collection.
local HeistCollect = {}

function HeistCollect.propose(view, settings)
    if type(settings) ~= "table" or settings.enabled ~= true then
        return nil, "Heist result collection disabled"
    end
    if type(view) ~= "table" or view.state ~= "result" then
        return nil, "No personal Heist result ready"
    end
    if view.resultAddressable ~= true then
        return nil, "Result identity unverified; collect manually"
    end
    return nil, "Heist mutation sequence ownership unverified"
end

return HeistCollect
