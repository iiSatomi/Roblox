-- No collect baseline is valid until result and sequence contracts are proven.
local HeistCollectEvidence = {}

function HeistCollectEvidence.capture()
    return nil, "Heist collection contract unverified"
end

function HeistCollectEvidence.evaluate()
    return "pending"
end

return HeistCollectEvidence
