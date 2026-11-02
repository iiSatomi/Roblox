-- Build separate profile and strict checkpoint stores from injected file primitives.
local StorageAssembly = {}

local function safeRoot(value)
    if type(value) ~= "string" or #value == 0 or #value > 160
        or value:sub(1, 1) == "/" or value:find("\\", 1, true)
        or value:find("//", 1, true) then return false end
    for segment in value:gmatch("[^/]+") do
        if segment == "." or segment == ".."
            or not segment:match("^[%w_.%-]+$") then return false end
    end
    return true
end

function StorageAssembly.new(deps)
    if type(deps) ~= "table" or type(deps.RedundantStore) ~= "table"
        or type(deps.RedundantStore.new) ~= "function"
        or type(deps.files) ~= "table"
        or type(deps.files.EnsureDirectory) ~= "function"
        or type(deps.files.ReadFile) ~= "function"
        or type(deps.files.WriteFile) ~= "function"
        or type(deps.codec) ~= "table"
        or type(deps.codec.Encode) ~= "function"
        or type(deps.codec.Decode) ~= "function"
        or type(deps.sha256) ~= "function"
        or not safeRoot(deps.directory) then
        return nil, "Missing or unsafe storage adapter"
    end
    local roots = { deps.directory, deps.directory .. "/profiles",
        deps.directory .. "/checkpoints" }
    for _, path in ipairs(roots) do
        local ok, made = pcall(deps.files.EnsureDirectory, deps.files, path)
        if not ok or made == false then
            return nil, "Storage directory unavailable"
        end
    end
    local ok, profiles = pcall(deps.RedundantStore.new, deps.files,
        deps.codec, deps.sha256, roots[2])
    if not ok then return nil, "Profile storage unavailable" end
    local strict, checkpoints = pcall(deps.RedundantStore.new,
        deps.files, deps.codec, deps.sha256, roots[3],
        { strictRecovery = true })
    if not strict or checkpoints.strictRecovery ~= true then
        return nil, "Strict checkpoint storage unavailable"
    end
    -- This stable account/place record survives fresh chunks and process restarts.
    -- It protects releases adopted here; it cannot discover older unindexed scopes.
    if deps.activateStorage == true or deps.identity ~= nil then
        local identity = deps.identity
        if type(identity) ~= "table" then return nil, "Missing storage identity" end
        for _, field in ipairs({ "account", "place", "release" }) do
            local value = identity[field]
            if type(value) ~= "string" or #value == 0 or #value > 160 then
                return nil, "Invalid storage identity"
            end
        end
        -- Known Fluent files can contain uncertain actions, custody and usage.
        -- Never treat a new Ember directory as proof these records disappeared.
        local legacyRoot = "IdleMafiaFluent/" .. identity.place .. "/" .. identity.account .. "/"
        for _, name in ipairs({ "settings", "configs", "action-journal", "market-flip", "market-sell", "market-memory", "property-review", "gear-plan" }) do
            local read, data = pcall(deps.files.ReadFile, deps.files, legacyRoot .. name .. ".json")
            if not read then return nil, "Legacy state discovery failed" end
            if data ~= nil then return nil, "Legacy " .. name .. " state requires explicit migration review" end
        end
        local key = "idle-mafia-ember:release-owner:v1:"
            .. #identity.account .. ":" .. identity.account
            .. #identity.place .. ":" .. identity.place
        local read, previous = pcall(checkpoints.Read, checkpoints, key)
        if not read then return nil, "Checkpoint release ownership unreadable" end
        if previous ~= nil then
            if type(previous) ~= "table" or previous.version ~= 1
                or previous.account ~= identity.account or previous.place ~= identity.place
                or type(previous.release) ~= "string" or #previous.release == 0
                or #previous.release > 160 then
                return nil, "Invalid checkpoint release ownership"
            end
            if previous.release ~= identity.release then
                return nil, "Checkpoint release changed; explicit migration required"
            end
        else
            local discovered, keys, discoveryReason = pcall(checkpoints.ListKeys, checkpoints)
            if not discovered or not keys then return nil, discoveryReason or "Checkpoint discovery unavailable" end
            local tag = #identity.account .. ":" .. identity.account .. #identity.place .. ":" .. identity.place
            for _, savedKey in ipairs(keys) do
                local body = savedKey:match("^idle%-mafia%-ember:[%w%-]+:v%d+:(.*)$")
                if body and body:sub(1, #tag) == tag and savedKey ~= key then
                    local length, rest = body:sub(#tag + 1):match("^(%d+):(.*)$")
                    length = tonumber(length)
                    if not length or length < 1 or length > 160 or #rest < length
                        or #rest > length and rest:sub(length + 1, length + 1) ~= ":" then
                        return nil, "Unindexed checkpoint scope requires migration review"
                    end
                    if rest:sub(1, length) ~= identity.release then return nil, "Unindexed checkpoint release requires explicit migration" end
                end
                local read, data = pcall(checkpoints.Read, checkpoints, savedKey)
                if not read then return nil, "Discovered checkpoint is unreadable" end
                if type(data) == "table" and data.account == identity.account and data.place == identity.place
                    and data.release ~= identity.release then return nil, "Saved receipt scope requires explicit migration" end
            end
            local saved, accepted = pcall(checkpoints.Write, checkpoints, key,
                { version = 1, account = identity.account,
                    place = identity.place, release = identity.release })
            if not saved or accepted ~= true then
                return nil, "Checkpoint release ownership was not confirmed"
            end
        end
    end
    return { ProfileStorage = profiles, storage = checkpoints }, nil
end

return StorageAssembly
