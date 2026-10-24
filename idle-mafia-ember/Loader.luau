-- Inert release loader. Fetch, cache, SHA-256 and compiler are injected adapters.
local Loader = {}
local active = nil
local starting = false

local function signature(commit, order)
    local parts = { commit }
    for _, entry in ipairs(order) do
        parts[#parts + 1] = entry.id .. ":" .. entry.path .. ":" .. entry.sha256
            .. ":" .. table.concat(entry.deps, ",")
    end
    return table.concat(parts, "|")
end

local function matches(bytes, digest, sha256)
    if type(bytes) ~= "string" then return false end
    local ok, actual = pcall(sha256, bytes)
    return ok and actual == digest
end

local function fail(reason)
    starting = false
    return nil, reason
end

function Loader.start(fetch, cache, compile, manifest, dependencies)
    if starting then return nil, "Initialization in progress" end
    if type(fetch) ~= "function" or type(cache) ~= "table"
        or type(cache.Read) ~= "function" or type(cache.Write) ~= "function"
        or type(compile) ~= "function" or type(dependencies) ~= "table"
        or type(dependencies.Manifest) ~= "table"
        or type(dependencies.Manifest.inspect) ~= "function"
        or type(dependencies.Manifest.validate) ~= "function"
        or type(dependencies.sha256) ~= "function"
        or type(dependencies.expectedCommit) ~= "string"
        or not dependencies.expectedCommit:match("^[0-9a-f]+$")
        or #dependencies.expectedCommit ~= 40 then
        return nil, "Missing loader adapter"
    end
    if type(manifest) ~= "table"
        or manifest.releaseCommit ~= dependencies.expectedCommit then
        return nil, "Release commit differs from bootstrap pin"
    end
    local order, reason = dependencies.Manifest.inspect(manifest)
    if not order then return nil, reason end
    local release = signature(manifest.releaseCommit, order)
    if active and active.app.alive == false then active = nil end
    if active then
        if active.signature == release then return active.app, nil end
        return nil, "Another release is running"
    end
    starting = true
    local bytesByPath, fetched = {}, {}
    for _, entry in ipairs(order) do
        local fetchedOk, fromFetch = pcall(fetch, manifest.releaseCommit, entry.path)
        local bytes = fetchedOk and fromFetch or nil
        if matches(bytes, entry.sha256, dependencies.sha256) then
            fetched[#fetched + 1] = { path = entry.path, bytes = bytes }
        else
            local cachedOk, fromCache = pcall(cache.Read, cache,
                manifest.releaseCommit, entry.path)
            bytes = cachedOk and fromCache or nil
            if not matches(bytes, entry.sha256, dependencies.sha256) then
                return fail("Missing or mismatched module: " .. entry.id)
            end
        end
        bytesByPath[entry.path] = bytes
    end
    local validated, validationReason = dependencies.Manifest.validate(
        manifest, bytesByPath, dependencies.sha256)
    if not validated then return fail(validationReason) end

    local chunks = {}
    for _, entry in ipairs(validated) do
        local ok, chunk = pcall(compile, bytesByPath[entry.path], entry.path)
        if not ok or type(chunk) ~= "function" then
            return fail("Module compile failed: " .. entry.id)
        end
        chunks[entry.id] = chunk
    end
    for _, item in ipairs(fetched) do
        pcall(cache.Write, cache, manifest.releaseCommit, item.path, item.bytes)
    end

    local exports = {}
    for _, entry in ipairs(validated) do
        local ok, value = pcall(chunks[entry.id])
        if not ok or type(value) ~= "table" then
            return fail("Module initialization failed: " .. entry.id)
        end
        exports[entry.id] = value
    end
    if type(exports.App) ~= "table" or type(exports.App.start) ~= "function" then
        return fail("App export missing")
    end
    local appDependencies = {}
    for key, value in pairs(dependencies) do appDependencies[key] = value end
    for key, value in pairs(exports) do appDependencies[key] = value end
    local starter = exports.App.start
    if dependencies.activateRuntimeHost == true then
        if type(exports.RuntimeHost) ~= "table"
            or type(exports.RuntimeHost.start) ~= "function" then
            return fail("Runtime host export missing")
        end
        starter = exports.RuntimeHost.start
    end
    local ok, app, startReason = pcall(starter, appDependencies)
    if not ok or type(app) ~= "table" then
        local detail = ok and type(startReason) == "string"
            and #startReason <= 120 and startReason or nil
        return fail(detail and ("App startup failed: " .. detail)
            or "App startup failed")
    end
    active = { signature = release, app = app }
    starting = false
    return app, nil
end

function Loader.close()
    if not active then return false end
    local app = active.app
    if type(app.Destroy) == "function" then
        local ok, result = pcall(app.Destroy, app)
        if not ok or result == false then return false end
    end
    active = nil
    return true
end

return Loader
