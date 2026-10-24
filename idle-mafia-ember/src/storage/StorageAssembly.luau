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
    return { ProfileStorage = profiles, storage = checkpoints }, nil
end

return StorageAssembly
