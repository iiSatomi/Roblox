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

-- Crew predates length-prefixed keys and keeps identity inside its envelope.
-- Validate that scope against the exact producer key; never split on colons.
local crewPrefix = "idle-mafia-ember:crew-replacement:"
local function crewDiscoveryReason(key, data, identity)
    local scope = type(data) == "table" and data.scope
    if type(scope) ~= "table" or data.schema ~= 1
        or type(data.generation) ~= "number" or data.generation < 1
        or data.generation > 9007199254740991 or data.generation % 1 ~= 0 then
        return "Invalid Crew checkpoint requires migration review"
    end
    for _, field in ipairs({"account", "place", "release", "ownerId"}) do
        local value = scope[field]
        if type(value) ~= "string" or #value == 0
            or #value > (field == "ownerId" and 120 or 200) then
            return "Invalid Crew checkpoint scope requires migration review"
        end
    end
    for field in pairs(scope) do
        if field ~= "account" and field ~= "place" and field ~= "release" and field ~= "ownerId" then
            return "Unknown Crew checkpoint scope requires migration review"
        end
    end
    local expected = crewPrefix .. "v1:" .. scope.account .. ":" .. scope.place .. ":" .. scope.release
    local sideKey = expected .. ":adapter-unsent:" .. string.format("%.0f", data.generation)
    if key ~= expected and key ~= sideKey then
        return "Crew checkpoint key/scope mismatch requires migration review"
    end
    -- Check the known envelope shape here; the Crew owner validates its contents.
    if key == expected then
        if type(data.usage) ~= "table"
            or data.active ~= nil and type(data.active) ~= "table"
            or data.resolution ~= nil and type(data.resolution) ~= "table" then
            return "Invalid Crew checkpoint schema requires migration review"
        end
    elseif type(data.proposal) ~= "table" or type(data.baseline) ~= "table" then
        return "Invalid Crew receipt schema requires migration review"
    end
    local allowed = key == expected
        and {schema=true, scope=true, generation=true, active=true, usage=true, resolution=true}
        or {schema=true, scope=true, generation=true, proposal=true, baseline=true}
    for field in pairs(data) do
        if not allowed[field] then return "Unknown Crew checkpoint schema requires migration review" end
    end
    local currentPrefix = crewPrefix .. "v1:" .. identity.account .. ":" .. identity.place .. ":"
    local sameAccount = scope.account == identity.account and scope.place == identity.place
    if not sameAccount and key:sub(1, #currentPrefix) == currentPrefix then
        return "Ambiguous Crew checkpoint scope requires migration review"
    end
    if sameAccount and scope.release ~= identity.release then
        return "Crew checkpoint release requires explicit migration"
    end
    return nil
end

-- Only a genuinely empty legacy checkpoint can be acknowledged without ledger conversion.
local function emptyCheckpoint(data)
    if type(data) ~= "table" or data.version ~= 1
        or type(data.records) ~= "table" or next(data.records) ~= nil then return false end
    for field in pairs(data) do
        if field ~= "version" and field ~= "records" and field ~= "familyClaimUsage" then return false end
    end
    if data.familyClaimUsage ~= nil then
        local usage = data.familyClaimUsage
        if type(usage) ~= "table" or type(usage.weeks) ~= "table" or next(usage.weeks) ~= nil then return false end
        for field in pairs(usage) do if field ~= "weeks" then return false end end
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
        local reviewPath = deps.directory .. "/migration-review.json"
        local readReview, reviewBytes = pcall(deps.files.ReadFile, deps.files, reviewPath)
        if not readReview then return nil, "Migration review unreadable" end
        local review
        if reviewBytes ~= nil then
            if type(reviewBytes) ~= "string" or #reviewBytes > 1048576 then return nil, "Invalid migration review" end
            local decoded, value = pcall(deps.codec.Decode, deps.codec, reviewBytes)
            if not decoded or type(value) ~= "table" or value.version ~= 1
                or value.account ~= identity.account or value.place ~= identity.place or value.release ~= identity.release
                or value.preserveLegacyHistory ~= true or type(value.legacy) ~= "table"
                or type(value.checkpoints) ~= "table" then return nil, "Migration review scope changed" end
            review = value
        end
        local reviewedFiles, reviewedKeys = {}, {}
        local function matches(bytes, expected)
            if type(bytes) ~= "string" or type(expected) ~= "string" or #expected ~= 64 then return false end
            local ok, digest = pcall(deps.sha256, bytes)
            return ok and digest == expected
        end
        local function acknowledged(key, data)
            if not review or not key:match("^idle%-mafia%-ember:checkpoint:v1:") or not emptyCheckpoint(data) then return false end
            local ok, current = pcall(checkpoints.Current, checkpoints, key)
            if not ok or not current or not matches(current.payload, review.checkpoints[key]) then return false end
            reviewedKeys[key] = review.checkpoints[key]
            return true
        end
        -- Known Fluent files can contain uncertain actions, custody and usage.
        -- Never treat a new Ember directory as proof these records disappeared.
        local legacyRoot = "IdleMafiaFluent/" .. identity.place .. "/" .. identity.account .. "/"
        local legacyFiles = {}
        for _, name in ipairs({ "settings", "configs", "action-journal", "market-flip", "market-sell", "market-memory", "property-review", "gear-plan", "high-value-targets", "combat-evidence" }) do
            legacyFiles[#legacyFiles + 1] = {path = legacyRoot .. name .. ".json", label = name}
        end
        legacyFiles[#legacyFiles + 1] = {path = legacyRoot .. "configs.json.bak", label = "config backup"}
        legacyFiles[#legacyFiles + 1] = {path = "IdleMafiaMugTracker/" .. identity.account .. "/mugs.json", label = "mug history"}
        for _, file in ipairs(legacyFiles) do
            local read, data = pcall(deps.files.ReadFile, deps.files, file.path)
            if not read then return nil, "Legacy state discovery failed" end
            if data ~= nil then
                if not review or not matches(data, review.legacy[file.path]) then
                    return nil, "Legacy " .. file.label .. " state requires explicit migration review"
                end
                reviewedFiles[file.path] = data
            end
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
        end
        -- An earlier adoption is not proof that no older owner wrote later.
        -- Recheck bounded discovery on every startup before accepting this scope.
        local discovered, keys, discoveryReason = pcall(checkpoints.ListKeys, checkpoints)
        if not discovered or not keys then return nil, discoveryReason or "Checkpoint discovery unavailable" end
        local tag = #identity.account .. ":" .. identity.account .. #identity.place .. ":" .. identity.place
        for _, savedKey in ipairs(keys) do
            local read, data = pcall(checkpoints.Read, checkpoints, savedKey)
            if not read then return nil, "Discovered checkpoint is unreadable" end
            local isCrew = savedKey:sub(1, #crewPrefix) == crewPrefix
            if isCrew then
                local reason = crewDiscoveryReason(savedKey, data, identity)
                if reason then return nil, reason end
            end
            local body = not isCrew and savedKey:match("^idle%-mafia%-ember:[%w%-]+:v%d+:(.*)$")
            if body and body:sub(1, #tag) == tag and savedKey ~= key then
                local length, rest = body:sub(#tag + 1):match("^(%d+):(.*)$")
                length = tonumber(length)
                if not length or length < 1 or length > 160 or #rest < length
                    or #rest > length and rest:sub(length + 1, length + 1) ~= ":" then
                    return nil, "Unindexed checkpoint scope requires migration review"
                end
                if rest:sub(1, length) ~= identity.release and not (#rest == length and acknowledged(savedKey, data)) then return nil, "Unindexed checkpoint release requires explicit migration" end
            end
            if type(data) == "table" and data.account == identity.account and data.place == identity.place
                and data.release ~= identity.release then return nil, "Saved receipt scope requires explicit migration" end
        end
        -- Verify the reviewed sources again before creating any release ownership record.
        if review then
            local ok, current = pcall(deps.files.ReadFile, deps.files, reviewPath)
            if not ok or current ~= reviewBytes then return nil, "Migration review changed" end
            for path, bytes in pairs(reviewedFiles) do
                local read, latest = pcall(deps.files.ReadFile, deps.files, path)
                if not read or latest ~= bytes then return nil, "Legacy source changed during migration review" end
            end
            for key, expected in pairs(reviewedKeys) do
                local read, latest = pcall(checkpoints.Current, checkpoints, key)
                if not read or not latest or not matches(latest.payload, expected) or not emptyCheckpoint(latest.value) then
                    return nil, "Old checkpoint changed during migration review"
                end
            end
        end
        if previous == nil then
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
