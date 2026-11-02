-- Validated account-local profiles over an injected atomic table store.
local ProfileStore = {}
local Methods = {}
local writers = setmetatable({}, { __mode = "k" })
Methods.__index = Methods

local function nonempty(value)
    return type(value) == "string" and #value > 0
end

local function validName(value)
    return type(value) == "string" and #value > 0
        and #value <= 32
        and value:match("^[%w_-]+$") ~= nil
end

local function copyProfile(profile)
    local values = {}
    for key, value in pairs(profile.values) do values[key] = value end
    return { schema = 1, values = values }
end

function ProfileStore.new(storage, model, account, place, launchStorage)
    assert(type(storage) == "table"
        and type(storage.Read) == "function"
        and type(storage.Write) == "function",
        "Missing atomic profile storage")
    assert(type(model) == "table"
        and type(model.Validate) == "function",
        "Missing settings validator")
    assert(nonempty(account) and nonempty(place),
        "Missing profile scope")
    return setmetatable({ storage = storage, launchStorage = launchStorage or storage, model = model,
        account = account, place = place,
        key = "idle-mafia-ember:profiles:v1:"
            .. #account .. ":" .. account
            .. #place .. ":" .. place }, Methods)
end

function Methods:ScopeKey()
    return self.key
end

local function selectionStore(self, suffix)
    local storage = (suffix == ":next" or suffix == ":sync") and self.launchStorage or self.storage
    if (suffix == ":next" or suffix == ":sync") and storage.strictRecovery == false then
        return nil, "Profile launch preferences require strict recovery storage"
    end
    return storage, nil
end
local function readSelection(self, suffix, label)
    local storage, reason = selectionStore(self, suffix)
    if not storage then return nil, reason end
    local ok, data = pcall(storage.Read, storage, self.key .. suffix)
    if not ok then return nil, label .. " read failed" end
    if data == nil then return nil, nil end
    if type(data) ~= "table" or data.version ~= 1
        or data.account ~= self.account or data.place ~= self.place
        or type(data.name) ~= "string"
        or (data.name ~= "" and not validName(data.name)) then
        return nil, "Corrupt " .. string.lower(label) .. " setting"
    end
    return data.name ~= "" and data.name or nil, nil
end
local function writeSelection(self, suffix, label, name)
    local storage, reason = selectionStore(self, suffix)
    if not storage then return false, reason end
    if name ~= nil then
        if not validName(name) then return false, "Invalid profile name" end
        local profile
        profile, reason = self:Load(name)
        if not profile then return false, reason end
    end
    local ok, result = pcall(storage.Write, storage, self.key .. suffix, {
        version = 1, account = self.account,
        place = self.place, name = name or "",
    })
    if not ok or result == false then return false, label .. " write failed" end
    return true, nil
end
function Methods:GetAutoload() return readSelection(self, ":autoload", "Autoload") end
function Methods:SetAutoload(name) return writeSelection(self, ":autoload", "Autoload", name) end
function Methods:GetNextLoad() return readSelection(self, ":next", "Next-launch choice") end
function Methods:SetNextLoad(name) return writeSelection(self, ":next", "Next-launch choice", name) end
function Methods:ConsumeNextLoad()
    local name, reason = self:GetNextLoad()
    if reason or not name then return nil, reason end
    local saved
    saved, reason = writeSelection(self, ":next", "Next-launch choice", nil)
    if not saved then return nil, reason end
    return name, nil
end

function Methods:GetSync()
    local storage, reason = selectionStore(self, ":sync")
    if not storage then return false, reason end
    local ok, data = pcall(storage.Read, storage, self.key .. ":sync")
    if not ok then return false, "Profile sync preference read failed" end
    if data == nil then return false, nil end
    if type(data) ~= "table" or data.version ~= 1 or data.account ~= self.account
        or data.place ~= self.place or type(data.enabled) ~= "boolean" then
        return false, "Corrupt profile sync preference"
    end
    return data.enabled, nil
end
function Methods:SetSync(enabled)
    if type(enabled) ~= "boolean" then return false, "Choose a profile sync setting" end
    local storage, reason = selectionStore(self, ":sync")
    if not storage then return false, reason end
    local ok, result = pcall(storage.Write, storage, self.key .. ":sync", {
        version = 1, account = self.account, place = self.place, enabled = enabled,
    })
    if not ok or result == false then return false, "Profile sync preference write failed" end
    return true, nil
end

function Methods:ReadAll()
    local ok, data = pcall(self.storage.Read,
        self.storage, self.key)
    if not ok then return nil, "Profile read failed" end
    if data == nil then return {} end
    if type(data) ~= "table" or data.version ~= 1
        or data.account ~= self.account
        or data.place ~= self.place
        or type(data.profiles) ~= "table" then
        return nil, "Corrupt profile store"
    end
    local profiles, count = {}, 0
    for name, profile in pairs(data.profiles) do
        count = count + 1
        if count > 16 or not validName(name)
            or type(profile) ~= "table"
            or type(profile.values) ~= "table" then
            return nil, "Corrupt profile store"
        end
        local keys = 0
        for _ in pairs(profile.values) do keys = keys + 1 end
        local valid = keys <= 512 and self.model:Validate(profile)
        if not valid then return nil, "Corrupt profile store" end
        profiles[name] = copyProfile(profile)
    end
    return profiles, nil
end

function Methods:List()
    local profiles, reason = self:ReadAll()
    if not profiles then return nil, reason end
    local names = {}
    for name in pairs(profiles) do names[#names + 1] = name end
    table.sort(names)
    return names, nil
end

function Methods:Load(name)
    if not validName(name) then return nil, "Invalid profile name" end
    local profiles, reason = self:ReadAll()
    if not profiles then return nil, reason end
    local profile = profiles[name]
    if not profile then return nil, "Profile not found" end
    return copyProfile(profile), nil
end

function Methods:Save(name, profile)
    if not validName(name) or type(profile) ~= "table"
        or type(profile.values) ~= "table" then
        return false, "Invalid profile"
    end
    local count = 0
    for _ in pairs(profile.values) do count = count + 1 end
    if count > 512 or not self.model:Validate(profile) then
        return false, "Invalid profile"
    end
    local profiles, reason = self:ReadAll()
    if not profiles then return false, reason end
    local current = 0
    for _ in pairs(profiles) do current = current + 1 end
    if not profiles[name] and current >= 16 then
        return false, "Profile capacity reached"
    end
    profiles[name] = copyProfile(profile)
    local ok, result = pcall(self.storage.Write, self.storage,
        self.key, { version = 1, account = self.account,
            place = self.place, profiles = profiles })
    if not ok or result == false then
        return false, "Profile write failed"
    end
    return true, nil
end

local function accountFromKey(key)
    local prefix = "idle-mafia-ember:profiles:v1:"
    if type(key) ~= "string" or key:sub(1, #prefix) ~= prefix then return nil end
    local function field(text)
        local length, rest = text:match("^(%d+):(.*)$")
        length = tonumber(length)
        if not length or length < 1 or length > 160 or #rest < length then return nil end
        return rest:sub(1, length), rest:sub(length + 1)
    end
    local account, rest = field(key:sub(#prefix + 1))
    if not account then return nil end
    local place, suffix = field(rest)
    if not place or suffix ~= "" and suffix ~= ":autoload" then return nil end
    return account, place
end
function Methods:AccountOverview()
    if type(self.storage.ListKeys) ~= "function" then return nil, "Account discovery unavailable" end
    local ok, keys = pcall(self.storage.ListKeys, self.storage)
    if not ok or type(keys) ~= "table" or #keys > 512 then return nil, "Account discovery unavailable" end
    local accounts = {}
    for _, key in ipairs(keys) do
        local account, place = accountFromKey(key)
        if account and place == self.place then accounts[account] = true end
    end
    local names = {}
    for account in pairs(accounts) do names[#names + 1] = account end
    table.sort(names, function(a, b)
        if a == self.account then return true end
        if b == self.account then return false end
        return a < b
    end)
    local result = { rows = {}, truncated = #names > 25 }
    for index = 1, math.min(#names, 25) do
        local account = names[index]
        local other = ProfileStore.new(self.storage, self.model, account, self.place, self.launchStorage)
        local profiles, profileReason = other:List()
        local autoload, autoloadReason = other:GetAutoload()
        local once, onceReason = other:GetNextLoad()
        local unavailable = profileReason or autoloadReason or onceReason
        if autoload and not other:Load(autoload) or once and not other:Load(once) then unavailable = "Missing selected profile" end
        result.rows[#result.rows + 1] = { account = account, profiles = profiles and #profiles or 0,
            autoload = not unavailable and autoload or nil,
            once = not unavailable and once or nil,
            status = unavailable and "Unavailable: saved choices could not be validated" or "Available" }
    end
    return result, nil
end

-- Selection references must be cleared before changing the saved profile identity.
function Methods:Rename(name, replacement)
    if not validName(name) or not validName(replacement) or name == replacement then
        return false, "Choose two different valid profile names"
    end
    local autoload, reason = self:GetAutoload()
    if reason then return false, reason end
    if autoload == name then return false, "Disable autoload before renaming this profile" end
    local nextLoad
    nextLoad, reason = self:GetNextLoad()
    if reason then return false, reason end
    if nextLoad == name then return false, "Clear next-launch choice before renaming this profile" end
    local profiles
    profiles, reason = self:ReadAll()
    if not profiles then return false, reason end
    if not profiles[name] then return false, "Profile not found" end
    if profiles[replacement] then return false, "Replacement name already exists" end
    profiles[replacement], profiles[name] = profiles[name], nil
    local ok, result = pcall(self.storage.Write, self.storage,
        self.key, { version = 1, account = self.account,
            place = self.place, profiles = profiles })
    if not ok or result == false then return false, "Profile rename write failed" end
    return true, nil
end

function Methods:Delete(name, expected)
    if not validName(name) then return false, "Invalid profile name" end
    local autoload, reason = self:GetAutoload()
    if reason then return false, reason end
    local nextLoad
    nextLoad, reason = self:GetNextLoad()
    if reason then return false, reason end
    if autoload == name or nextLoad == name then
        return false, "Clear launch selections before deleting this profile"
    end
    local profiles
    profiles, reason = self:ReadAll()
    if not profiles then return false, reason end
    local current = profiles[name] and self.model:Validate(profiles[name], true)
    local reviewed = self.model:Validate(expected, true)
    if not current or not reviewed then return false, "Preview the saved profile before deletion" end
    for key, value in pairs(current) do
        if reviewed[key] ~= value then return false, "Saved profile changed; preview it again" end
    end
    profiles[name] = nil
    local ok, result = pcall(self.storage.Write, self.storage, self.key,
        { version = 1, account = self.account, place = self.place, profiles = profiles })
    if not ok or result == false then return false, "Profile deletion write failed" end
    return true, nil
end

-- File adapters may yield. Hold the whole read/validate/write operation, including
-- selection references, so an overlapping edit cannot replace a stale profile map.
for _, name in ipairs({ "Save", "Rename", "Delete", "SetAutoload", "SetNextLoad", "ConsumeNextLoad", "SetSync" }) do
    local method = Methods[name]
    Methods[name] = function(self, ...)
        local scopes = writers[self.storage]
        if not scopes then scopes = {}; writers[self.storage] = scopes end
        if scopes[self.key] then
            if name == "ConsumeNextLoad" then return nil, "Profile update already in progress" end
            return false, "Profile update already in progress"
        end
        scopes[self.key], self.writing = self, true
        local result = table.pack(pcall(method, self, ...))
        scopes[self.key], self.writing = nil, false
        if not result[1] then
            if name == "ConsumeNextLoad" then return nil, "Profile update failed" end
            return false, "Profile update failed"
        end
        return table.unpack(result, 2, result.n)
    end
end

return ProfileStore
