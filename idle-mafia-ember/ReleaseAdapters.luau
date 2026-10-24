-- Fetch and cache only modules under one reviewed repository commit.
-- Loader independently verifies the SHA-256 of every returned byte string.
local ReleaseAdapters = {}
local origin = "https://raw.githubusercontent.com/iiSatomi/Roblox/"
local cacheRoot = "IdleMafiaEmber/modules"
local maxModuleBytes = 1000000

local function validCommit(value)
    return type(value) == "string" and #value == 40
        and value:match("^[0-9a-f]+$") ~= nil
end

local function validPath(path)
    if type(path) ~= "string" or #path > 220
        or path:sub(1, 4) ~= "src/"
        or path:sub(-5) ~= ".luau"
        or path:find("//", 1, true)
        or path:find("\\", 1, true) then
        return false
    end
    for segment in path:gmatch("[^/]+") do
        if segment == "." or segment == ".."
            or not segment:match("^[%w_.%-]+$") then
            return false
        end
    end
    return true
end

local function ensureFolder(api, path)
    local current = ""
    for segment in path:gmatch("[^/]+") do
        current = current == "" and segment
            or current .. "/" .. segment
        local checked, exists = pcall(api.isfolder, current)
        if not checked then return false end
        if not exists then
            local made = pcall(api.makefolder, current)
            local verified, nowExists = pcall(api.isfolder, current)
            if not made or not verified or not nowExists then
                return false
            end
        end
    end
    return true
end

function ReleaseAdapters.new(commit, api)
    if not validCommit(commit) or type(api) ~= "table"
        or type(api.httpGet) ~= "function"
        or type(api.isfolder) ~= "function"
        or type(api.makefolder) ~= "function"
        or type(api.isfile) ~= "function"
        or type(api.readfile) ~= "function"
        or type(api.writefile) ~= "function"
        or type(api.compile) ~= "function" then
        return nil, "Missing pinned release adapters"
    end
    local function safe(requestCommit, path)
        return requestCommit == commit and validPath(path)
    end
    local function cachePath(path)
        return cacheRoot .. "/" .. commit .. "/" .. path
    end
    local cache = {}
    function cache:Read(requestCommit, path)
        if not safe(requestCommit, path) then return nil end
        local full = cachePath(path)
        local checked, exists = pcall(api.isfile, full)
        if not checked or not exists then return nil end
        local read, bytes = pcall(api.readfile, full)
        if not read or type(bytes) ~= "string"
            or #bytes > maxModuleBytes then return nil end
        return bytes
    end
    function cache:Write(requestCommit, path, bytes)
        if not safe(requestCommit, path)
            or type(bytes) ~= "string"
            or #bytes > maxModuleBytes then return false end
        local full = cachePath(path)
        local directory = full:match("^(.+)/[^/]+$")
        if not directory or not ensureFolder(api, directory) then
            return false
        end
        local written = pcall(api.writefile, full, bytes)
        return written and self:Read(requestCommit, path) == bytes
    end
    local function fetch(requestCommit, path)
        if not safe(requestCommit, path) then return nil end
        local url = origin .. commit .. "/idle-mafia-ember/" .. path
        local fetched, bytes = pcall(api.httpGet, url)
        if not fetched or type(bytes) ~= "string"
            or #bytes > maxModuleBytes then return nil end
        return bytes
    end
    local function compile(bytes, path)
        if type(bytes) ~= "string" or not validPath(path) then
            return nil
        end
        return api.compile(bytes, "@" .. path)
    end
    return { fetch = fetch, cache = cache,
        compile = compile }, nil
end

return ReleaseAdapters
