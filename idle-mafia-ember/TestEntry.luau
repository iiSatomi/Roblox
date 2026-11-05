-- Pinned UI smoke test. Runtime/gameplay activation is always false.
local sourceCommit = "b5dbbd676a95f4399532d06b6d692ba23bcc674b"
local manifestCommit = "5e590919630219d8280a4e5ec5e5265eeb5cd32d"
local root = "https://raw.githubusercontent.com/iiSatomi/Roblox/"
local project = "/idle-mafia-ember/"
local hashApi = crypt or (syn and syn.crypt)
assert(type(hashApi) == "table" and type(hashApi.hash) == "function", "SHA-256 API unavailable")
assert(type(loadstring) == "function", "loadstring unavailable")

local function fetch(url, expected, label)
    local ok, bytes = pcall(function() return game:HttpGet(url) end)
    assert(ok and type(bytes) == "string", "Fetch failed: " .. label)
    local hashed, digest = pcall(hashApi.hash, bytes, "sha256")
    assert(hashed and type(digest) == "string" and digest:lower() == expected,
        "SHA-256 mismatch: " .. label)
    return bytes
end

local function pinnedModule(path, digest)
    local bytes = fetch(root .. sourceCommit .. project .. path, digest, path)
    local chunk, reason = loadstring(bytes, "@" .. path)
    assert(type(chunk) == "function", reason or "Compile failed: " .. path)
    local module = chunk()
    assert(type(module) == "table", "Invalid module: " .. path)
    return module
end

local manifestBytes = fetch(root .. manifestCommit .. project .. "manifest.json",
    "6e62043c2b5d302714cf283d4c5d72fba35b472015a5bcc668836b24514c4c05", "manifest")
local manifest = game:GetService("HttpService"):JSONDecode(manifestBytes)
assert(manifest.releaseCommit == sourceCommit, "Manifest pin mismatch")

local Loader = pinnedModule("Loader.luau", "2bd90f28042eccb649fb02d2617ff2d5770f2c74cba97b4968bbac629340fbb4")
local Manifest = pinnedModule("src/loader/Manifest.luau", "4f6209df6e75fba086626d7ad466222b292b39e84be170d20d67fa12ca447cf4")
local Bootstrap = pinnedModule("Bootstrap.luau", "43ca5ff4333dd4258150c4a5ad3ea296b0586478e7de5b95daedbdbc99b6ac56")
local ReleaseAdapters = pinnedModule("ReleaseAdapters.luau", "83e94688a7b2262e43e764ea36ef1271afda91d8f9f7808fd1aa347622eb4b3c")
local ExecutorEntry = pinnedModule("ExecutorEntry.luau", "ce746884d2cd0994e96e8da8690ffdb5086f7794b6f3957611a84828197bd090")

-- Official Ember URL is mutable. Reject an update until its bytes are reviewed.
local emberBytes = fetch("https://rbx.lol/ember.lua",
    "0aebb331911619d0c791de1d0d3e9b2e51ead3fb4472cd038807155ad8bcf412", "Ember 3.0.0")
local emberChunk, emberReason = loadstring(emberBytes, "@Ember.lua")
assert(type(emberChunk) == "function", emberReason or "Ember compile failed")
local Ember = emberChunk()
assert(type(Ember) == "table", "Ember did not return a library")

-- Keep cache memory-only when file primitives are unavailable.
local files, folders = {}, {}
local disk = type(isfolder) == "function" and type(makefolder) == "function"
    and type(isfile) == "function" and type(readfile) == "function"
    and type(writefile) == "function"
local env = {
    crypt = hashApi,
    -- Genuine read capabilities only; memory cache fallback is not account storage.
    savedStateReadApi = { isfile=isfile, readfile=readfile, listfiles=listfiles },
    isfolder = disk and isfolder or function(path) return folders[path] == true end,
    makefolder = disk and makefolder or function(path) folders[path] = true end,
    isfile = disk and isfile or function(path) return files[path] ~= nil end,
    readfile = disk and readfile or function(path) return files[path] end,
    writefile = disk and writefile or function(path, bytes) files[path] = bytes end,
}
local app, reason = ExecutorEntry.start({
    commit = sourceCommit, manifest = manifest,
    place = "73897506680154", gameVersion = "0.26.646.1",
    fingerprint = "610c43e492f5fbb12e9dd38665031fefe3b6584b3a336de0203cea2e68b1bc08",
    directory = "IdleMafiaEmber",
}, {
    ReleaseAdapters = ReleaseAdapters, Bootstrap = Bootstrap,
    Loader = Loader, Manifest = Manifest, executorEnv = env,
    httpGet = function(url) return game:HttpGet(url) end,
    compile = loadstring, clientGame = game, clientRequire = require,
    scheduler = {}, Ember = Ember,
}, false)
assert(app, reason or "UI startup failed")
return app
