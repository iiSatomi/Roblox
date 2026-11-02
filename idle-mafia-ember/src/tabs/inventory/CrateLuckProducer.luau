-- Bind a current native crate luck calculation to one full Sync.
local CrateLuckProducer = {}

local function valid(value)
    return type(value) == "number" and value == value
        and value >= 0 and value <= 10
end

function CrateLuckProducer.derive(raw, context, source)
    local native = type(raw) == "table" and raw.native
    if type(context) ~= "table" or type(source) ~= "table"
        or type(source.Read) ~= "function"
        or type(native) ~= "table" or native.fullSync ~= true
        or source.release ~= context.release
        or raw.session ~= context.session
        or raw.account ~= context.account
        or raw.place ~= context.place
        or raw.release ~= context.release
        or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt then
        return nil, "Fresh native crate luck source required"
    end
    local ok, luck = pcall(source.Read, source, native)
    if not ok or not valid(luck) then
        return nil, "Invalid current crate luck"
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision,
        capturedAt = context.capturedAt, luck = luck }, nil
end

return CrateLuckProducer
