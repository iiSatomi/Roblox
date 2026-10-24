-- Validated account-local profiles over an injected atomic table store.
local ProfileStore = {}
local Methods = {}
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

function ProfileStore.new(storage, model, account, place)
    assert(type(storage) == "table"
        and type(storage.Read) == "function"
        and type(storage.Write) == "function",
        "Missing atomic profile storage")
    assert(type(model) == "table"
        and type(model.Validate) == "function",
        "Missing settings validator")
    assert(nonempty(account) and nonempty(place),
        "Missing profile scope")
    return setmetatable({ storage = storage, model = model,
        account = account, place = place,
        key = "idle-mafia-ember:profiles:v1:"
            .. #account .. ":" .. account
            .. #place .. ":" .. place }, Methods)
end

function Methods:ScopeKey()
    return self.key
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

return ProfileStore
