-- Saved Config.BANK.depositFee copied for a matching release/full Sync.
local NativeBankCatalog = {}
local Methods = {}
Methods.__index = Methods

function NativeBankCatalog.new(config, fingerprint, release)
    local fee = type(config) == "table"
        and type(config.BANK) == "table"
        and config.BANK.depositFee
    assert(type(fee) == "number" and fee == fee
        and fee >= 0 and fee <= 1
        and type(fingerprint) == "string" and #fingerprint == 64
        and fingerprint:match("^[%x]+$")
        and type(release) == "string" and #release > 0,
        "Missing reviewed Bank fee source")
    return setmetatable({ release = release,
        key = fingerprint:lower(), fee = fee }, Methods)
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" or snapshot.release ~= self.release
        or type(snapshot.native) ~= "table"
        or snapshot.native.fullSync ~= true then
        return nil, "Bank fee needs a matching full Sync"
    end
    local result = {}
    for key, value in pairs(snapshot) do result[key] = value end
    result.bankConfig = { release = self.release,
        catalogKey = self.key, depositFee = self.fee }
    return result, nil
end

return NativeBankCatalog
