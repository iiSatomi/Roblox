-- Release entry point. The caller supplies reviewed pins and narrow services.
-- A missing explicit activation starts only the inert App.
local Bootstrap = {}
local abcSha256 = "ba7816bf8f01cfea414140de5dae2223b00361a396"
    .. "177a9cb410ff61f20015ad"

local function hex(value, length)
    return type(value) == "string" and #value == length
        and value:match("^[0-9a-f]+$") ~= nil
end

local ownerKey = "__IDLE_MAFIA_EMBER_EXECUTION_V1"
local function acquire(release, registry, account, legacyRegistry)
    if type(registry)~="table" then return nil,"Runtime ownership registry unavailable" end
    if legacyRegistry ~= nil and type(legacyRegistry) ~= "table" then
        return nil, "Legacy execution registry unavailable"
    end
    if rawget(registry, "IdleMafiaFluentHub") ~= nil
        or legacyRegistry and rawget(legacyRegistry, "IdleMafiaFluentHub") ~= nil then
        return nil, "Legacy Fluent execution or pending receipts require review before Ember activation"
    end
    local previous=rawget(registry,ownerKey)
    if previous~=nil then
        if type(previous)~="table" or previous.version~=1 or previous.account~=account
            or previous.place~=release.place or type(previous.release)~="string"
            or not hex(previous.release,40)
            or type(previous.writes)~="number" or previous.writes~=previous.writes
            or previous.writes<0 or previous.writes>=math.huge or previous.writes%1~=0 then return nil,"Existing runtime ownership is ambiguous" end
        if previous.release~=release.commit then return nil,"Previous release requires checkpoint migration before replacement" end
        if previous.writes>0 then return nil,"Existing runtime is writing; wait before replacing it" end
        if previous.phase=="starting" or previous.phase=="closing" then return nil,"Runtime startup or shutdown already in progress" end
        if previous.phase=="active" then
            local handle=previous.handle
            if type(handle)~="table" or type(handle.CanReplace)~="function" or type(handle.Destroy)~="function" then
                return nil,"Existing runtime ownership cannot be safely replaced"
            end
            local checked,allowed,why=pcall(handle.CanReplace,handle)
            if not checked or allowed~=true then return nil,checked and why or "Existing runtime replacement check failed" end
            if rawget(registry,ownerKey)~=previous then return nil,"Execution ownership changed during replacement check" end
            if previous.writes>0 then return nil,"Existing runtime is writing; wait before replacing it" end
            previous.phase="closing"
            local closed=pcall(handle.Destroy,handle)
            if not closed or handle.alive~=false then previous.phase="fault";return nil,"Existing runtime did not confirm shutdown" end
            previous.phase="closed"
        elseif previous.phase~="closed" then return nil,"Existing runtime ownership needs review"
        elseif previous.handle and previous.handle.alive~=false then return nil,"Closed runtime ownership is ambiguous" end
    end
    if rawget(registry,ownerKey)~=previous then return nil,"Execution ownership changed during shutdown" end
    local record={version=1,account=account,place=release.place,release=release.commit,phase="starting",writes=0}
    rawset(registry,ownerKey,record)
    return record,nil
end
local function guardedEnvironment(env, registry, record)
    local result={}
    for key,value in pairs(env) do result[key]=value end
    if type(env.writefile)=="function" then
        result.writefile=function(...)
            if rawget(registry,ownerKey)~=record or (record.phase~="starting" and record.phase~="active") then
                error("Execution owner changed; file write refused",0)
            end
            record.writes=record.writes+1
            local values=table.pack(pcall(env.writefile,...))
            record.writes=record.writes-1
            if not values[1] then error(values[2],0) end
            return table.unpack(values,2,values.n)
        end
    end
    return result
end

function Bootstrap.start(release, adapters, activateRuntime)
    if activateRuntime == true
        and (type(release) ~= "table"
            or type(release.allowedFeatures) ~= "table"
            or next(release.allowedFeatures) == nil) then
        return nil, "Functional release needs an explicit feature allowlist"
    end
    if type(release) ~= "table" or type(adapters) ~= "table"
        or not hex(release.commit, 40)
        or not hex(release.fingerprint, 64)
        or type(release.place) ~= "string"
        or type(release.gameVersion) ~= "string"
        or #release.gameVersion == 0
        or type(release.directory) ~= "string"
        or type(release.manifest) ~= "table"
        or release.manifest.releaseCommit ~= release.commit
        or type(adapters.Loader) ~= "table"
        or type(adapters.Loader.start) ~= "function"
        or type(adapters.Manifest) ~= "table"
        or type(adapters.fetch) ~= "function"
        or type(adapters.cache) ~= "table"
        or type(adapters.compile) ~= "function"
        or type(adapters.clientRequire) ~= "function"
        or type(adapters.clientHash) ~= "function"
        or type(adapters.Ember) ~= "table"
        or adapters.clientGame == nil then
        return nil, "Missing pinned release or bootstrap adapters"
    end
    local inspected, place, player, http = pcall(function()
        local game = adapters.clientGame
        local players = game:GetService("Players")
        return game.PlaceId, players.LocalPlayer,
            game:GetService("HttpService")
    end)
    if not inspected or tostring(place) ~= release.place
        or player == nil or type(player.Name) ~= "string"
        or #player.Name == 0 then
        return nil, "Current client identity unavailable or wrong place"
    end
    if activateRuntime == true
        and (type(adapters.executorEnv) ~= "table"
            or type(adapters.scheduler) ~= "table"
            or http == nil) then
        return nil, "Current executor services unavailable"
    end
    local hashed, digest = pcall(adapters.clientHash,
        "abc", "sha256")
    if not hashed or type(digest) ~= "string"
        or digest:lower() ~= abcSha256 then
        return nil, "Bootstrap SHA-256 unavailable"
    end
    local sessionId
    if activateRuntime == true then
        local generated, value = pcall(http.GenerateGUID, http, false)
        if not generated or type(value) ~= "string"
            or #value == 0 or #value > 80 then
            return nil, "Current session identity unavailable"
        end
        sessionId = value
    end
    local owner,ownerReason
    local executorEnv=adapters.executorEnv
    if activateRuntime==true then
        owner,ownerReason=acquire(release,adapters.executionRegistry,player.Name,adapters.legacyRegistry)
        if not owner then return nil,ownerReason end
        executorEnv=guardedEnvironment(executorEnv,adapters.executionRegistry,owner)
    end
    local dependencies = {
        Manifest = adapters.Manifest,
        sha256 = function(bytes)
            return adapters.clientHash(bytes, "sha256")
        end,
        expectedCommit = release.commit,
        expectedGameVersion = release.gameVersion,
        fingerprint = release.fingerprint,
        release = release.commit,
        allowedFeatures = activateRuntime == true
            and release.allowedFeatures or nil,
        directory = release.directory,
        Ember = adapters.Ember,
        identity = { place = release.place, account = player.Name,
            release = release.commit, session = sessionId },
        activateRuntimeHost = activateRuntime == true,
        activateAutomation = activateRuntime == true,
        activateStorage = activateRuntime == true,
        activateCurrentClient = activateRuntime == true,
        clientGame = adapters.clientGame,
        clientRequire = adapters.clientRequire,
        clientHash = adapters.clientHash,
        executorEnv = executorEnv,
        scheduler = adapters.scheduler,
        httpService = http,
    }
    if not owner then return adapters.Loader.start(adapters.fetch,adapters.cache,adapters.compile,release.manifest,dependencies) end
    local ok,handle,reason=pcall(adapters.Loader.start,adapters.fetch,adapters.cache,adapters.compile,release.manifest,dependencies)
    local current=rawget(adapters.executionRegistry,ownerKey)==owner
    if not ok or type(handle)~="table" or handle.alive~=true or type(handle.Destroy)~="function"
        or type(handle.CanReplace)~="function" or not current then
        local cleaned=type(handle)~="table" or handle.alive~=true
        if type(handle)=="table" and type(handle.Destroy)=="function" then
            cleaned=pcall(handle.Destroy,handle) and handle.alive==false
        end
        owner.phase=cleaned and "closed" or "fault"
        return nil,ok and (reason or "Runtime startup returned invalid ownership handle") or "Runtime startup raised"
    end
    owner.handle,owner.phase=handle,"active"
    return handle,nil
end

return Bootstrap
