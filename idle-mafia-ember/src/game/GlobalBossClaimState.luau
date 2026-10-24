-- Claim view needs a settled personal result and local send ledger.
local GlobalBossClaimState = {}

function GlobalBossClaimState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing Global Boss claim input"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Global Boss claim snapshot changed"
        end
    end
    local boss, usage = context.globalBoss,
        raw.globalClaimUsageProof
    if type(boss) ~= "table" or boss.status ~= "known"
        or type(boss.runKey) ~= "string"
        or type(usage) ~= "table"
        or usage.account ~= context.account
        or usage.capturedAt ~= context.capturedAt
        or usage.runKey ~= boss.runKey
        or type(usage.attempts) ~= "number"
        or usage.attempts < 0 or usage.attempts > 1
        or usage.attempts % 1 ~= 0 then
        return nil, "Current Global Boss claim proof required"
    end
    local view = {}
    for key, value in pairs(boss) do view[key] = value end
    view.attempts = usage.attempts
    return view, nil
end

return GlobalBossClaimState
