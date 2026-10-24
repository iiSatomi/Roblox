-- Pure validation only. The caller supplies a trusted SHA-256 implementation.
local Manifest = {}

local function hex(value, length)
    return type(value) == "string" and #value == length
        and string.match(value, "^[0-9a-f]+$") ~= nil
end

local function arrayLength(raw)
    if type(raw) ~= "table" then return nil end
    local size = #raw
    for key in pairs(raw) do
        if type(key) ~= "number" or key % 1 ~= 0
            or key < 1 or key > size then return nil end
    end
    for index = 1, size do
        if raw[index] == nil then return nil end
    end
    return size
end

local function safePath(value)
    if type(value) ~= "string" or value:sub(1, 4) ~= "src/"
        or value:sub(-5) ~= ".luau" or value:find("//", 1, true) then
        return false
    end
    for segment in value:gmatch("[^/]+") do
        if segment == "." or segment == ".."
            or not segment:match("^[%w_.%-]+$") then return false end
    end
    return true
end

function Manifest.inspect(raw)
    if type(raw) ~= "table" or raw.schema ~= 1
        or not hex(raw.releaseCommit, 40) then
        return nil, "Invalid manifest header"
    end
    local count = arrayLength(raw.modules)
    if not count or count == 0 or count > 256 then
        return nil, "Invalid module list"
    end
    local byId, byPath, entries = {}, {}, {}
    for index, module in ipairs(raw.modules) do
        if type(module) ~= "table" or type(module.id) ~= "string"
            or not module.id:match("^[%w_]+$") or not safePath(module.path)
            or not hex(module.sha256, 64) then
            return nil, "Invalid module entry"
        end
        if byId[module.id] or byPath[module.path] then
            return nil, "Duplicate module ID or path"
        end
        local depCount = arrayLength(module.deps)
        if not depCount then return nil, "Invalid dependency list" end
        local deps, seenDeps = {}, {}
        for depIndex, dependency in ipairs(module.deps) do
            if type(dependency) ~= "string" or not dependency:match("^[%w_]+$")
                or seenDeps[dependency] then
                return nil, "Invalid or duplicate dependency"
            end
            seenDeps[dependency] = true
            deps[depIndex] = dependency
        end
        local entry = {
            id = module.id, path = module.path, sha256 = module.sha256,
            deps = deps,
        }
        byId[entry.id], byPath[entry.path], entries[index] = entry, true, entry
    end
    local order, visiting, visited = {}, {}, {}
    local function visit(id)
        if visiting[id] then return false, "Dependency cycle" end
        if visited[id] then return true end
        local entry = byId[id]
        if not entry then return false, "Missing dependency" end
        visiting[id] = true
        for _, dependency in ipairs(entry.deps) do
            local ok, reason = visit(dependency)
            if not ok then return false, reason end
        end
        visiting[id], visited[id] = nil, true
        order[#order + 1] = entry
        return true
    end
    for _, entry in ipairs(entries) do
        local ok, reason = visit(entry.id)
        if not ok then return nil, reason end
    end
    return order, nil
end

function Manifest.validate(raw, bytesByPath, sha256)
    local order, reason = Manifest.inspect(raw)
    if not order then return nil, reason end
    if type(bytesByPath) ~= "table" or type(sha256) ~= "function" then
        return nil, "Missing module bytes or hash provider"
    end
    for _, entry in ipairs(order) do
        local bytes = bytesByPath[entry.path]
        if type(bytes) ~= "string" then return nil, "Missing module bytes" end
        local ok, digest = pcall(sha256, bytes)
        if not ok or not hex(digest, 64) or digest ~= entry.sha256 then
            return nil, "Module hash mismatch"
        end
    end
    return order, nil
end

return Manifest
