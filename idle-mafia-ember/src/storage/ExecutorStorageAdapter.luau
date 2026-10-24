-- Wrap ordinary executor file/JSON/hash primitives without guessing support.
local ExecutorStorageAdapter = {}

local function safePath(value)
    if type(value) ~= "string" or #value == 0
        or #value > 240 or value:find("\\", 1, true)
        or value:sub(1, 1) == "/"
        or value:find("//", 1, true) then return false end
    for segment in value:gmatch("[^/]+") do
        if segment == "." or segment == ".."
            or not segment:match("^[%w_.%-]+$") then
            return false
        end
    end
    return true
end

function ExecutorStorageAdapter.new(api)
    if type(api) ~= "table" or type(api.isfolder) ~= "function"
        or type(api.makefolder) ~= "function"
        or type(api.isfile) ~= "function"
        or type(api.readfile) ~= "function"
        or type(api.writefile) ~= "function"
        or type(api.jsonEncode) ~= "function"
        or type(api.jsonDecode) ~= "function"
        or type(api.hash) ~= "function" then
        return nil, "Missing executor storage capability"
    end
    local files = {}
    function files:EnsureDirectory(path)
        if not safePath(path) then return false end
        local prefix = ""
        for segment in path:gmatch("[^/]+") do
            prefix = prefix == "" and segment
                or prefix .. "/" .. segment
            local checked, exists = pcall(api.isfolder, prefix)
            if not checked then return false end
            if exists ~= true then
                local made = pcall(api.makefolder, prefix)
                if not made then return false end
                checked, exists = pcall(api.isfolder, prefix)
                if not checked or exists ~= true then
                    return false
                end
            end
        end
        return true
    end
    function files:ReadFile(path)
        if not safePath(path) then error("Unsafe storage path") end
        if not api.isfile(path) then return nil end
        local result = api.readfile(path)
        if type(result) ~= "string" then
            error("Invalid executor file read")
        end
        return result
    end
    function files:WriteFile(path, value)
        if not safePath(path) or type(value) ~= "string"
            or #value > 2097152 then return false end
        api.writefile(path, value)
        return api.isfile(path) == true
    end
    local codec = {}
    function codec:Encode(value)
        local result = api.jsonEncode(value)
        if type(result) ~= "string" then
            error("Invalid executor JSON encode")
        end
        return result
    end
    function codec:Decode(value)
        if type(value) ~= "string" then
            error("Invalid executor JSON input")
        end
        return api.jsonDecode(value)
    end
    local function sha256(value)
        local result = api.hash(value)
        if type(result) ~= "string" or #result ~= 64
            or not result:match("^[%x]+$") then
            error("SHA-256 unavailable")
        end
        return result:lower()
    end
    return { files = files, codec = codec,
        sha256 = sha256 }, nil
end

return ExecutorStorageAdapter
