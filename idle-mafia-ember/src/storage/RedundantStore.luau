-- Two checked slots for decoded-table state; primitives are injected.
local RedundantStore = {}
local Methods = {}
Methods.__index = Methods

local function digest(hash, value)
    local ok, result = pcall(hash, value)
    if not ok or type(result) ~= "string" or #result ~= 64
        or result:match("^[%x]+$") == nil then return nil end
    return string.lower(tostring(result))
end

local function validKey(key)
    return type(key) == "string" and #key > 0 and #key <= 512
end

function RedundantStore.new(files, codec, hash, directory, options)
    assert(type(files) == "table"
        and type(files.ReadFile) == "function"
        and type(files.WriteFile) == "function", "Missing file primitives")
    assert(type(codec) == "table"
        and type(codec.Encode) == "function"
        and type(codec.Decode) == "function", "Missing JSON codec")
    assert(type(hash) == "function", "Missing SHA-256 primitive")
    assert(type(directory) == "string" and #directory > 0,
        "Missing storage directory")
    assert(options == nil or (type(options) == "table"
        and (options.strictRecovery == nil
            or type(options.strictRecovery) == "boolean")),
        "Invalid storage recovery mode")
    return setmetatable({ files = files, codec = codec,
        hash = hash, directory = directory,
        strictRecovery = options ~= nil and options.strictRecovery == true }, Methods)
end

function Methods:Paths(key)
    if not validKey(key) then error("Invalid storage key") end
    local id = digest(self.hash, key)
    if not id then error("Storage hash unavailable") end
    local prefix = self.directory .. "/" .. id
    return prefix .. ".a.json", prefix .. ".b.json"
end

function Methods:Slot(path, key)
    local ok, text = pcall(self.files.ReadFile, self.files, path)
    if not ok then return { status = "error" } end
    if text == nil then return { status = "missing" } end
    if type(text) ~= "string" or #text > 2097152 then
        return { status = "bad" }
    end
    local decoded, envelope = pcall(self.codec.Decode,
        self.codec, text)
    if not decoded or type(envelope) ~= "table"
        or envelope.version ~= 1 or envelope.key ~= key
        or type(envelope.generation) ~= "number"
        or envelope.generation < 1
        or envelope.generation % 1 ~= 0
        or envelope.generation == math.huge
        or type(envelope.payload) ~= "string"
        or #envelope.payload > 1048576
        or type(envelope.digest) ~= "string" then
        return { status = "bad" }
    end
    local expected = digest(self.hash, key .. ":"
        .. tostring(envelope.generation) .. ":" .. envelope.payload)
    if not expected or string.lower(tostring(envelope.digest)) ~= expected then
        return { status = "bad" }
    end
    local payloadOk, value = pcall(self.codec.Decode,
        self.codec, envelope.payload)
    if not payloadOk or type(value) ~= "table" then
        return { status = "bad" }
    end
    return { status = "valid", generation = envelope.generation,
        payload = envelope.payload, value = value }
end

function Methods:Current(key)
    local firstPath, secondPath = self:Paths(key)
    local first = self:Slot(firstPath, key)
    local second = self:Slot(secondPath, key)
    if first.status == "error" or second.status == "error" then
        error("Storage read failed")
    end
    -- A damaged inactive slot may contain a newer committed attempt.
    -- Checkpoint callers choose strict recovery so it cannot disappear.
    if self.strictRecovery and (first.status == "bad"
        or second.status == "bad") then
        error("Damaged strict storage slot")
    end
    if first.status == "valid" and second.status == "valid"
        and first.generation == second.generation
        and first.payload ~= second.payload then
        error("Conflicting storage generations")
    end
    if first.status == "valid" and (second.status ~= "valid"
        or first.generation >= second.generation) then
        return first, secondPath
    end
    if second.status == "valid" then return second, firstPath end
    if first.status == "missing" and second.status == "missing" then
        return nil, firstPath
    end
    error("No valid storage slot")
end

function Methods:Read(key)
    local current = self:Current(key)
    return current and current.value or nil
end

-- Discovery is read-only and bounded; a damaged slot cannot establish absence.
function Methods:ListKeys()
    if type(self.files.ListFiles) ~= "function" then return nil, "Storage discovery unavailable" end
    local ok, paths = pcall(self.files.ListFiles, self.files, self.directory)
    if not ok or type(paths) ~= "table" or #paths > 512 then return nil, "Storage discovery unavailable or exceeds limits" end
    local seenPaths, keys, bytes, count = {}, {}, 0, 0
    for index, path in pairs(paths) do
        if type(index) ~= "number" or index % 1 ~= 0 or index < 1 or index > #paths
            or type(path) ~= "string" or seenPaths[path]
            or path:sub(1, #self.directory + 1) ~= self.directory .. "/" then
            return nil, "Invalid storage discovery path"
        end
        seenPaths[path] = true
        count = count + 1
        local name = path:sub(#self.directory + 2)
        if name:find("/", 1, true) or name:find("\\", 1, true) then return nil, "Invalid storage discovery path" end
        local id = name:match("^([%da-f]+)%.[ab]%.json$")
        if id and #id == 64 then
            local read, text = pcall(self.files.ReadFile, self.files, path)
            if not read or type(text) ~= "string" or #text > 2097152 then return nil, "Unreadable discovered storage slot" end
            bytes = bytes + #text
            if bytes > 16777216 then return nil, "Storage discovery exceeds byte limit" end
            local decoded, envelope = pcall(self.codec.Decode, self.codec, text)
            if not decoded or type(envelope) ~= "table" or not validKey(envelope.key) then
                return nil, "Damaged discovered storage slot"
            end
            local first, second = self:Paths(envelope.key)
            if path ~= first and path ~= second then return nil, "Discovered storage path/hash mismatch" end
            if self:Slot(path, envelope.key).status ~= "valid" then return nil, "Damaged discovered storage slot" end
            keys[envelope.key] = true
        end
    end
    if count ~= #paths then return nil, "Sparse storage discovery" end
    local result = {}
    for key in pairs(keys) do
        local read, value = pcall(self.Read, self, key)
        if not read or value == nil then return nil, "Discovered storage cannot be recovered" end
        result[#result + 1] = key
    end
    table.sort(result)
    return result, nil
end

function Methods:Write(key, value)
    if type(value) ~= "table" then return false end
    local current, target = self:Current(key)
    local generation = current and current.generation + 1 or 1
    if generation > 9007199254740991 then return false end
    local ok, payload = pcall(self.codec.Encode, self.codec, value)
    if not ok or type(payload) ~= "string"
        or #payload > 1048576 then return false end
    local check = digest(self.hash, key .. ":"
        .. tostring(generation) .. ":" .. payload)
    if not check then return false end
    local encoded, envelope = pcall(self.codec.Encode, self.codec,
        { version = 1, key = key, generation = generation,
            payload = payload, digest = check })
    if not encoded or type(envelope) ~= "string"
        or #envelope > 2097152 then return false end
    local saved, result = pcall(self.files.WriteFile,
        self.files, target, envelope)
    if not saved or result == false then return false end
    local observed = self:Slot(target, key)
    return observed.status == "valid"
        and observed.generation == generation
        and observed.payload == payload
end

return RedundantStore
