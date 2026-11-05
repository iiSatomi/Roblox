-- Adapt verified executor primitives without file writes or remote calls.
local NativeExecutorCapabilities = {}

local abcSha256 = "ba7816bf8f01cfea414140de5dae2223b00361a396"
    .. "177a9cb410ff61f20015ad"

local function method(value, key)
    local ok, result = pcall(function() return value[key] end)
    return ok and type(result) == "function" and result or nil
end

function NativeExecutorCapabilities.new(env, scheduler, http)
    if type(env) ~= "table" or type(scheduler) ~= "table"
        or not method(env, "isfolder")
        or not method(env, "makefolder")
        or not method(env, "isfile")
        or not method(env, "readfile")
        or not method(env, "writefile")
        or not method(env.crypt, "hash")
        or not method(scheduler, "delay")
        or not method(scheduler, "cancel")
        or not method(scheduler, "defer")
        or not method(http, "JSONEncode")
        or not method(http, "JSONDecode") then
        return nil, "Missing executor capabilities"
    end
    local hashed, digest = pcall(env.crypt.hash, "abc", "sha256")
    if not hashed or type(digest) ~= "string"
        or digest:lower() ~= abcSha256 then
        return nil, "Executor SHA-256 unavailable"
    end
    local runtime = {
        after = function(delay, callback)
            return scheduler.delay(delay, callback)
        end,
        cancel = function(handle)
            return scheduler.cancel(handle)
        end,
        defer = function(callback)
            return scheduler.defer(callback)
        end,
    }
    if method(scheduler, "spawn") then
        -- Native game helpers can lower the calling thread's UI capabilities.
        -- Engine scheduling restores the owner context; coroutine.resume does not.
        runtime.readNative = function(callback, ...)
            if type(callback) ~= "function" then return false, "Invalid native read" end
            local args, result, completed = table.pack(...), nil, false
            local started, thread = pcall(scheduler.spawn, function()
                result = table.pack(pcall(callback, table.unpack(args, 1, args.n)))
                completed = true
            end)
            if not started then return false, thread end
            if not completed then
                if thread ~= nil then pcall(scheduler.cancel, thread) end
                return false, "Native calculation yielded"
            end
            return table.unpack(result, 1, result.n)
        end
    end
    local storage = {
        isfolder = env.isfolder,
        makefolder = env.makefolder,
        isfile = env.isfile,
        readfile = env.readfile,
        listfiles = method(env, "listfiles"),
        writefile = env.writefile,
        jsonEncode = function(value)
            return http:JSONEncode(value)
        end,
        jsonDecode = function(value)
            return http:JSONDecode(value)
        end,
        hash = function(value)
            return env.crypt.hash(value, "sha256")
        end,
    }
    local clock = { Now = function() return os.clock() end }
    return { executorRuntimeApi = runtime,
        executorStorageApi = storage, clock = clock }, nil
end

return NativeExecutorCapabilities
