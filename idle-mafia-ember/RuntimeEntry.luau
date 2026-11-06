-- Current-client runtime: all switches start off; explicit profile autoload may enable them.
local sourceCommit = "491ca8967867a50b4170ccd852da6257f4777ab8"
local manifestCommit = "8df2342c0118e11c048661759fa61d6988da4ae2"
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
    "be13483d5c359ade626c4a32cc12a74a98f8bc36c90ee90fcbac086b22ac1a25", "manifest")
local manifest = game:GetService("HttpService"):JSONDecode(manifestBytes)
assert(manifest.releaseCommit == sourceCommit, "Manifest pin mismatch")

local Loader = pinnedModule("Loader.luau", "2bd90f28042eccb649fb02d2617ff2d5770f2c74cba97b4968bbac629340fbb4")
local Manifest = pinnedModule("src/loader/Manifest.luau", "4f6209df6e75fba086626d7ad466222b292b39e84be170d20d67fa12ca447cf4")
local Bootstrap = pinnedModule("Bootstrap.luau", "eb9cc2eb7d377e132f2d1f627580c5146b186ccb97b30bfad627952f2a2a5d5d")
local ReleaseAdapters = pinnedModule("ReleaseAdapters.luau", "83e94688a7b2262e43e764ea36ef1271afda91d8f9f7808fd1aa347622eb4b3c")
local ExecutorEntry = pinnedModule("ExecutorEntry.luau", "ce746884d2cd0994e96e8da8690ffdb5086f7794b6f3957611a84828197bd090")

-- Official Ember URL is mutable. Reject an update until its bytes are reviewed.
local emberBytes = fetch("https://rbx.lol/ember.lua",
    "0aebb331911619d0c791de1d0d3e9b2e51ead3fb4472cd038807155ad8bcf412", "Ember 3.0.0")
local emberChunk, emberReason = loadstring(emberBytes, "@Ember.lua")
assert(type(emberChunk) == "function", emberReason or "Ember compile failed")
local Ember = emberChunk()
assert(type(Ember) == "table", "Ember did not return a library")

local env = {
    crypt = hashApi,
    isfolder = isfolder, makefolder = makefolder,
    isfile = isfile, readfile = readfile, writefile = writefile, listfiles = listfiles,
    getupvalues = type(getupvalues) == "function" and getupvalues or nil,
}
local app, reason = ExecutorEntry.start({
    commit = sourceCommit, manifest = manifest,
    place = "73897506680154", gameVersion = "0.26.645.1",
    fingerprint = "7032df7733506f1f80739faca9c9d66d688d6d5a38b2a506b1e8de1fd6c22c78",
    directory = "IdleMafiaEmber",
    allowedFeatures = {
        jobs = true, operations = true, collect = true, heists = true,
        heistCollect = true, favors = true, sabotage = true, combat = true,
        warCombat = true, bosses = true, bossShop = true, crew = true,
        crewGear = true, crewRoll = true, crewSort = true, crewHeal = true,
        crewTrain = true, crewHire = true, crewHealItems = true, cosmetics = true,
        collectionDonate = true, chests = true, restoratives = true, bank = true,
        withdraw = true, properties = true, safehouse = true, prestige = true,
        shop = true, marketWatch = true, marketSell = true, marketFlip = true,
        marketRent = true, marketManage = true, familyCash = true, familyStamina = true,
        familyGold = true, familyBossAttacks = true, familyBossClaims = true, territoryWatch = true,
        station = true, residency = true, contracts = true, bonuses = true,
        trophies = true, skills = true, playtime = true, groupBonus = true,
        monthlyRewards = true, autoContracts = true, trophyFocus = true, globalBossAttack = true,
        globalBossClaim = true, briefcases = true, eventShop = true,
    },
}, {
    ReleaseAdapters = ReleaseAdapters, Bootstrap = Bootstrap,
    Loader = Loader, Manifest = Manifest, executorEnv = env, executionRegistry = _G,
    legacyRegistry = type(getgenv) == "function" and getgenv() or _G,
    httpGet = function(url) return game:HttpGet(url) end,
    compile = loadstring, clientGame = game, clientRequire = require,
    scheduler = task, Ember = Ember,
}, true)
assert(app, reason or "Runtime startup failed")
return app
