-- Saved MWClient feed shape: Sync event plus State.onChanged ticks.
local NativeEventAdapter = {}
local Methods = {}
Methods.__index = Methods

function NativeEventAdapter.new(syncSignal, state)
    local readable, connect = pcall(function()
        return syncSignal.Connect
    end)
    if not readable or type(connect) ~= "function"
        or type(state) ~= "table"
        or type(state.onChanged) ~= "function" then
        return nil, "Missing saved-client Sync or State feed"
    end
    return setmetatable({ syncSignal = syncSignal,
        state = state }, Methods), nil
end

function NativeEventAdapter.fromFolder(folder, state)
    local readable, find = pcall(function()
        return folder.FindFirstChild
    end)
    if not readable or type(find) ~= "function" then
        return nil, "Missing current Remotes folder"
    end
    local found, sync = pcall(folder.FindFirstChild, folder, "Sync")
    if not found or sync == nil then
        return nil, "Missing current Sync remote"
    end
    local valid, signal = pcall(function()
        if sync.Parent ~= folder or not sync:IsA("RemoteEvent") then
            return nil
        end
        return sync.OnClientEvent
    end)
    if not valid or signal == nil then
        return nil, "Invalid current Sync remote"
    end
    return NativeEventAdapter.new(signal, state)
end

function Methods:SubscribeSync(callback)
    if type(callback) ~= "function" then
        error("Invalid Sync callback")
    end
    local connection = self.syncSignal:Connect(callback)
    local readable, disconnect = pcall(function()
        return connection.Disconnect
    end)
    if not readable or type(disconnect) ~= "function" then
        error("Invalid Sync connection")
    end
    return connection
end

function Methods:SubscribeChanged(callback)
    if type(callback) ~= "function" then
        error("Invalid State callback")
    end
    local connection = self.state.onChanged(callback)
    local readable, disconnect = pcall(function()
        return connection.Disconnect
    end)
    if not readable or type(disconnect) ~= "function" then
        error("Invalid State connection")
    end
    return connection
end

return NativeEventAdapter
