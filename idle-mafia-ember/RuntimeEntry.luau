-- Current-client runtime: all switches start off; explicit profile autoload may enable them.
local sourceCommit = "2d00b865c55527f464670e8049d18dbce4bfa572"
local manifestCommit = "bb2000c8c84159e95de43f73e5c3d9a48ef60e2f"
local root = "https://raw.githubusercontent.com/iiSatomi/Roblox/"
local project = "/idle-mafia-ember/"
local hashApi = crypt or (syn and syn.crypt)
assert(type(hashApi) == "table" and type(hashApi.hash) == "function", "SHA-256 API unavailable")
assert(type(loadstring) == "function", "loadstring unavailable")
assert(type(task) == "table" and type(task.delay) == "function"
    and type(task.cancel) == "function" and type(task.defer) == "function",
    "Runtime scheduler unavailable")
assert(type(isfolder) == "function" and type(makefolder) == "function"
    and type(isfile) == "function" and type(readfile) == "function"
    and type(writefile) == "function", "Durable executor file storage unavailable")

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
    "94a21e51fa7f2c22640659d70fa9a82bc7b67bf86bd1df761ee55689482d9aee", "manifest")
local manifest = game:GetService("HttpService"):JSONDecode(manifestBytes)
assert(manifest.releaseCommit == sourceCommit, "Manifest pin mismatch")

local Loader = pinnedModule("Loader.luau", "a39df0bc554eee950c64d8d147e33a22698cd86f5376520c4b1086663f9298ba")
local Manifest = pinnedModule("src/loader/Manifest.luau", "cbbe6d580c1fab36bf8c9cd4d9e93830dee7c091a32a6fd9bf2a30868712822b")
local Bootstrap = pinnedModule("Bootstrap.luau", "8e532b4bb2e45255b75f66f249423a7f2e70d3ff954fd08f2780fb28c1237c99")
local ReleaseAdapters = pinnedModule("ReleaseAdapters.luau", "f830b6379ff3eeff3d0ad7942fbc9497f2a9989fcc0c212f744c66eed0494c8c")
local ExecutorEntry = pinnedModule("ExecutorEntry.luau", "6defd52943d4db8168be6f882abef9a12616b53c2bd0cc187ed21234b9cfc0e5")

-- Official Ember URL is mutable. Reject an update until its bytes are reviewed.
local emberBytes = fetch("https://rbx.lol/ember.lua",
    "c6ec2ad2ad732a2ed704d044fd068b685d7e6c2613f60a07c39316666576390a", "Ember 3.0.0")
local emberChunk, emberReason = loadstring(emberBytes, "@Ember.lua")
assert(type(emberChunk) == "function", emberReason or "Ember compile failed")
local Ember = emberChunk()
assert(type(Ember) == "table", "Ember did not return a library")

local env = {
    crypt = hashApi,
    isfolder = isfolder, makefolder = makefolder,
    isfile = isfile, readfile = readfile, writefile = writefile,
}
local app, reason = ExecutorEntry.start({
    commit = sourceCommit, manifest = manifest,
    place = "73897506680154", gameVersion = "0.26.530",
    fingerprint = "bebadc6d78d85af67403580b0e9d6e15f2032aaea30dcf5a2a71911ea4df4a7b",
    directory = "IdleMafiaEmber",
    allowedFeatures = { jobs = true, bosses = true },
}, {
    ReleaseAdapters = ReleaseAdapters, Bootstrap = Bootstrap,
    Loader = Loader, Manifest = Manifest, executorEnv = env,
    httpGet = function(url) return game:HttpGet(url) end,
    compile = loadstring, clientGame = game, clientRequire = require,
    scheduler = task, Ember = Ember,
}, true)
assert(app, reason or "Runtime startup failed")
return app
