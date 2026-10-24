-- Pinned UI smoke test. Runtime/gameplay activation is always false.
local sourceCommit = "c35cb73533668c930fc1269b70c4630f90a0def9"
local manifestCommit = "132a2917af8a8bc01f51669c672fee8c76d30ac5"
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
    "647fe1192809d067d35824ce09702744550709c07f77d3afc1ff6eace39c0782", "manifest")
local manifest = game:GetService("HttpService"):JSONDecode(manifestBytes)
assert(manifest.releaseCommit == sourceCommit, "Manifest pin mismatch")

local Loader = pinnedModule("Loader.luau", "4f09695d238d97d086f2e6badb0637fa181904c8c8c3614dbd2f57c1148ccd4a")
local Manifest = pinnedModule("src/loader/Manifest.luau", "cbbe6d580c1fab36bf8c9cd4d9e93830dee7c091a32a6fd9bf2a30868712822b")
local Bootstrap = pinnedModule("Bootstrap.luau", "2438d9caaa57a3e09cf2aca31a30cf1c58ef51fbba779afef5197c0d9537beb4")
local ReleaseAdapters = pinnedModule("ReleaseAdapters.luau", "f830b6379ff3eeff3d0ad7942fbc9497f2a9989fcc0c212f744c66eed0494c8c")
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
