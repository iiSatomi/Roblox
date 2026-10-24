-- Narrow asynchronous timer and native invocation capability wrapper.
local ExecutorRuntimeAdapter = {}

function ExecutorRuntimeAdapter.new(api)
    if type(api) ~= "table" or type(api.after) ~= "function"
        or type(api.cancel) ~= "function"
        or type(api.defer) ~= "function"
        or type(api.invoke) ~= "function" then
        return nil, "Missing executor runtime capability"
    end
    local timer = {}
    function timer:After(delay, callback)
        if type(delay) ~= "number" or delay < 0.25
            or delay > 5 or type(callback) ~= "function" then
            return nil
        end
        local scheduling = true
        local handle = api.after(delay, function()
            if scheduling then error("Timer ran synchronously") end
            callback()
        end)
        scheduling = false
        return handle
    end
    function timer:Cancel(handle)
        return api.cancel(handle)
    end
    local nativeExecutor = {}
    function nativeExecutor:Schedule(callback)
        if type(callback) ~= "function" then
            error("Invalid native dispatch callback")
        end
        local scheduling = true
        local result = api.defer(function()
            if scheduling then error("Dispatch ran synchronously") end
            callback()
        end)
        scheduling = false
        return result
    end
    function nativeExecutor:Invoke(remote, method, ...)
        if type(remote) ~= "string" or #remote == 0
            or method ~= "InvokeServer" then
            error("Invalid native invocation")
        end
        return api.invoke(remote, ...)
    end
    return { timer = timer,
        nativeExecutor = nativeExecutor }, nil
end

return ExecutorRuntimeAdapter
