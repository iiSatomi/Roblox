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

function NativeRemoteResolver.new(folder, lane, nativeLink)
    if not method(folder, "FindFirstChild") then
        return nil, "Missing current Remotes folder"
    end
    if lane ~= nil and (type(lane) ~= "table" or type(lane.Owns) ~= "function") then
        return nil, "Invalid native request lane"
    end
    if nativeLink ~= nil and (type(nativeLink) ~= "table" or type(nativeLink.Current) ~= "function"
        or type(nativeLink.Resolve) ~= "function") then return nil, "Invalid current native RemoteLink" end
    return setmetatable({ folder = folder, nativeLink = nativeLink, approved = {},
        linkCurrent = nativeLink and nativeLink.Current, linkResolve = nativeLink and nativeLink.Resolve,
        lane = lane, closed = false, invoking = nil }, Methods), nil
end

local function resolve(self, token, name, checkLease)
    if self.closed or type(name) ~= "string" or #name == 0
        or #name > 80 or not name:match("^[%w_]+$") then
        error("Invalid native remote name")
    end
    if checkLease and self.lane and not self.lane:Owns(token) then error("Native request lease unavailable") end
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
    local callable = remote
    if self.nativeLink then
        if self.nativeLink.Current ~= self.linkCurrent or self.nativeLink.Resolve ~= self.linkResolve then
            error("Native link functions changed")
        end
        local current, accepted = pcall(self.nativeLink.Current, self.nativeLink)
        if not current or accepted ~= true then error("Current native RemoteLink unavailable") end
        local resolved, wrapped = pcall(self.nativeLink.Resolve, self.nativeLink, name)
        if not resolved or wrapped == nil then error("Current native wrapped remote unavailable") end
        if wrapped ~= remote and (type(wrapped) ~= "table" or wrapped.Instance ~= remote
            or wrapped.Name ~= name or not method(wrapped, "InvokeServer")) then
            error("Current native remote wrapper mismatch")
        end
        local previous = self.approved[name]
        local fn = method(wrapped, "InvokeServer")
        if previous and (previous.instance ~= remote or previous.wrapper ~= wrapped or previous.invoke ~= fn) then
            error("Native wrapper binding changed")
        end
        self.approved[name] = previous or {instance = remote, wrapper = wrapped, invoke = fn}
        callable = wrapped
    end
    return callable
end

local function invoke(self, token, name, ...)
    local callable = resolve(self, token, name, true)
    if self.invoking and (not self.lane or self.lane:Owns(self.invoking.token)) then
        error("Native invocation already running")
    end
    if self.lane and not self.lane:Owns(token) then error("Native request lease expired") end
    local status = self.lane and type(self.lane.Status) == "function" and self.lane:Status()
    local read = status and status.active and status.active.kind == "read"
    local invocation = {token = token}
    self.invoking = invocation
    local result = table.pack(pcall(function(...)
        return callable:InvokeServer(...)
    end, ...))
    -- An old yielded call cannot clear the physical marker of a newer owner.
    if self.invoking == invocation then self.invoking = nil end
    if not result[1] then error(result[2], 0) end
    if read and not self:Current(name) then error("Native read source changed during invocation") end
    return table.unpack(result, 2, result.n)
end

function Methods:Current(name)
    local ok, callable = pcall(resolve, self, nil, name, false)
    return ok and callable ~= nil
end

function Methods:Invoke(name, ...)
    return invoke(self, nil, name, ...)
end

function Methods:InvokeOwned(token, name, ...)
    return invoke(self, token, name, ...)
end

function Methods:InFlight()
    return not self.closed and self.invoking ~= nil
        and (not self.lane or self.lane:Owns(self.invoking.token))
end

function Methods:Close()
    self.closed = true
end

return NativeRemoteResolver
