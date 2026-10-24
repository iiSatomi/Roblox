-- Resolve a currently parented RemoteFunction only at dispatch time.
local NativeRemoteResolver = {}
local Methods = {}
Methods.__index = Methods

local function method(value, key)
    local ok, result = pcall(function()
        return value[key]
    end)
    return ok and type(result) == "function" and result or nil
end

function NativeRemoteResolver.new(folder)
    if not method(folder, "FindFirstChild") then
        return nil, "Missing current Remotes folder"
    end
    return setmetatable({ folder = folder,
        closed = false }, Methods), nil
end

function Methods:Invoke(name, ...)
    if self.closed or type(name) ~= "string" or #name == 0
        or #name > 80 or not name:match("^[%w_]+$") then
        error("Invalid native remote name")
    end
    local remote = self.folder:FindFirstChild(name)
    local isA = method(remote, "IsA")
    local invoke = method(remote, "InvokeServer")
    local parentOk, parent = pcall(function()
        return remote.Parent
    end)
    if not isA or not invoke or not parentOk
        or parent ~= self.folder
        or remote:IsA("RemoteFunction") ~= true then
        error("Current native RemoteFunction unavailable")
    end
    return remote:InvokeServer(...)
end

function Methods:Close()
    self.closed = true
end

return NativeRemoteResolver
