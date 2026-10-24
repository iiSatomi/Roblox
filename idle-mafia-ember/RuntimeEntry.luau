-- Current-client runtime: all switches start off; explicit profile autoload may enable them.
local sourceCommit = "253c62fdc276ec11015a756287463bf6b000d65a"
local manifestCommit = "4fc0eeffbfdcda50ab36bb042b7cec579c29b4bc"
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
    "2fdccc1f4b646d063bf2d594d7ffb6fe5cbe7dfec2d322ec7e2a2a51927fed35", "manifest")
local manifest = game:GetService("HttpService"):JSONDecode(manifestBytes)
assert(manifest.releaseCommit == sourceCommit, "Manifest pin mismatch")

local Loader = pinnedModule("Loader.luau", "2bd90f28042eccb649fb02d2617ff2d5770f2c74cba97b4968bbac629340fbb4")
local Manifest = pinnedModule("src/loader/Manifest.luau", "cbbe6d580c1fab36bf8c9cd4d9e93830dee7c091a32a6fd9bf2a30868712822b")
local Bootstrap = pinnedModule("Bootstrap.luau", "65e35b03c92bed69575a5f70dfe7fa11045a3324b1f795598e837c7b8d90c146")
local ReleaseAdapters = pinnedModule("ReleaseAdapters.luau", "83e94688a7b2262e43e764ea36ef1271afda91d8f9f7808fd1aa347622eb4b3c")
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
    place = "73897506680154", gameVersion = "0.26.555.1",
    fingerprint = "36f6d88997e5315663632826ab69e562ca9eea3672aef2c07b14aed6a050d5d0",
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
