-- Release entry point. The caller supplies reviewed pins and narrow services.
-- A missing explicit activation starts only the inert App.
local Bootstrap = {}
local abcSha256 = "ba7816bf8f01cfea414140de5dae2223b00361a396"
    .. "177a9cb410ff61f20015ad"

local function hex(value, length)
    return type(value) == "string" and #value == length
        and value:match("^[0-9a-f]+$") ~= nil
end

function Bootstrap.start(release, adapters, activateRuntime)
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
    local dependencies = {
        Manifest = adapters.Manifest,
        sha256 = function(bytes)
            return adapters.clientHash(bytes, "sha256")
        end,
        expectedCommit = release.commit,
        expectedGameVersion = release.gameVersion,
        fingerprint = release.fingerprint,
        release = release.commit,
        directory = release.directory,
        Ember = adapters.Ember,
        identity = { place = release.place, account = player.Name },
        activateRuntimeHost = activateRuntime == true,
        activateAutomation = activateRuntime == true,
        activateStorage = activateRuntime == true,
        activateCurrentClient = activateRuntime == true,
        clientGame = adapters.clientGame,
        clientRequire = adapters.clientRequire,
        clientHash = adapters.clientHash,
        executorEnv = adapters.executorEnv,
        scheduler = adapters.scheduler,
        httpService = http,
    }
    return adapters.Loader.start(adapters.fetch, adapters.cache,
        adapters.compile, release.manifest, dependencies)
end

return Bootstrap
