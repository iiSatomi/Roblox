-- Pinned UI smoke test. Runtime/gameplay activation is always false.
local sourceCommit = "5ddbb9e1b04242bde62dd8a32abe5bc4a28f5857"
local manifestCommit = "06ac5c2b5d096a5042a5e457bb60dd75aa982a77"
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
    "dee91827a8602d7a814e53e43948819547dda49bd1481c9502f3122c7f218398", "manifest")
local manifest = game:GetService("HttpService"):JSONDecode(manifestBytes)
assert(manifest.releaseCommit == sourceCommit, "Manifest pin mismatch")

local Loader = pinnedModule("Loader.luau", "2bd90f28042eccb649fb02d2617ff2d5770f2c74cba97b4968bbac629340fbb4")
local Manifest = pinnedModule("src/loader/Manifest.luau", "cbbe6d580c1fab36bf8c9cd4d9e93830dee7c091a32a6fd9bf2a30868712822b")
local Bootstrap = pinnedModule("Bootstrap.luau", "8e532b4bb2e45255b75f66f249423a7f2e70d3ff954fd08f2780fb28c1237c99")
local ReleaseAdapters = pinnedModule("ReleaseAdapters.luau", "83e94688a7b2262e43e764ea36ef1271afda91d8f9f7808fd1aa347622eb4b3c")
local ExecutorEntry = pinnedModule("ExecutorEntry.luau", "6defd52943d4db8168be6f882abef9a12616b53c2bd0cc187ed21234b9cfc0e5")

-- Official Ember URL is mutable. Reject an update until its bytes are reviewed.
local emberBytes = fetch("https://rbx.lol/ember.lua",
    "c6ec2ad2ad732a2ed704d044fd068b685d7e6c2613f60a07c39316666576390a", "Ember 3.0.0")
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
    isfolder = disk and isfolder or function(path) return folders[path] == true end,
    makefolder = disk and makefolder or function(path) folders[path] = true end,
    isfile = disk and isfile or function(path) return files[path] ~= nil end,
    readfile = disk and readfile or function(path) return files[path] end,
    writefile = disk and writefile or function(path, bytes) files[path] = bytes end,
}
local app, reason = ExecutorEntry.start({
    commit = sourceCommit, manifest = manifest,
    place = "73897506680154", gameVersion = "0.26.530",
    fingerprint = "bebadc6d78d85af67403580b0e9d6e15f2032aaea30dcf5a2a71911ea4df4a7b",
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
