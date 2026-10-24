-- Paused current-client runtime. Actions require enabling a feature and Resume.
local sourceCommit = "1534654ae9e5ed9dd3911e60f2948c43236a63a8"
local manifestCommit = "3057b89085c89eb61411af43b69417b144076713"
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
    "71c6ecec5821c2befdaa8caec7ec4e374216bb6c5576f28ebc6e25e75bcbcaa0", "manifest")
local manifest = game:GetService("HttpService"):JSONDecode(manifestBytes)
assert(manifest.releaseCommit == sourceCommit, "Manifest pin mismatch")

local Loader = pinnedModule("Loader.luau", "b658ab217abbfb160e8bebc80abedf30543fe5bd7c3afa4cf8d9b1490a39b441")
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
