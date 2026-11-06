-- Native FamilyAction("browse", query). Display-only discovery: never membership evidence.
local Query, Methods = {}, {}
Methods.__index = Methods
local fields = {"session", "account", "place", "release", "revision", "capturedAt"}
local function copy(v)
    if type(v) ~= "table" then return v end
    local out = {}; for k, child in pairs(v) do out[k] = copy(child) end; return out
end
local function current(self)
    if self.closed or not self.enabled or not self.source or self.source.Current ~= self.current then return false end
    local ok, valid = pcall(self.current, self.source, "FamilyAction"); return ok and valid == true
end
local function same(self, raw, request)
    if not current(self) or request ~= self.request or request.query ~= self.query
        or type(raw) ~= "table" or type(raw.native) ~= "table" or raw.native.fullSync ~= true then return false end
    for _, key in ipairs(fields) do if raw[key] ~= request.header[key] then return false end end
    return raw.native.serverNow == request.serverNow
end
function Query.new(source)
    return setmetatable({source = source, current = type(source) == "table" and source.Current,
        query = "", enabled = false, closed = false}, Methods)
end
function Methods:Configure(settings)
    local enabled = type(settings) == "table" and settings.browse == true
    local query = type(settings) == "table" and settings.query or ""
    if type(query) ~= "string" or #query > 64 or query:find("[%c]") then enabled, query = false, "" end
    if self.query ~= query or self.enabled ~= enabled then self.request, self.staged = nil, nil end
    self.query, self.enabled = query, enabled
    return current(self)
end
function Methods:Prepare(raw)
    if not current(self) or type(raw) ~= "table" or type(raw.native) ~= "table" or raw.native.fullSync ~= true then return nil, "Family directory unavailable" end
    local header = {};for _, key in ipairs(fields) do header[key] = raw[key] end
    self.request = {remote = "FamilyAction", method = "InvokeServer", arity = 2, args = {"browse", self.query},
        query = self.query, header = header, serverNow = raw.native.serverNow}
    self.staged = nil
    return self.request, nil
end
function Methods:Accept(raw, request, reply)
    if not same(self, raw, request) or type(reply) ~= "table" or reply.ok ~= true
        or type(reply.families) ~= "table" or #reply.families > 512
        or type(reply.browseReady) ~= "boolean" then return nil, "Family directory reply unavailable or stale" end
    local rows, seen, count = {}, {}, 0
    for key, row in pairs(reply.families) do
        count = count + 1
        if type(key) ~= "number" or key % 1 ~= 0 or key < 1 or key > #reply.families
            or type(row) ~= "table" or type(row.id) ~= "string" or #row.id > 120
            or row.id == "0" or not row.id:match("^[%w_%-]+$") or seen[row.id]
            or type(row.name) ~= "string" or #row.name < 1 or #row.name > 120 or row.name:find("[%c]") then
            return nil, "Invalid Family directory rows"
        end
        seen[row.id] = true; rows[key] = {id = row.id, name = row.name}
    end
    if count ~= #reply.families then return nil, "Sparse Family directory" end
    table.sort(rows, function(a, b) return a.name == b.name and a.id < b.id or a.name < b.name end)
    self.staged = {rows = rows, ready = reply.browseReady, query = request.query, capturedAt = raw.capturedAt}
    self.prepared = copy(self.staged)
    return self.staged, nil
end
function Methods:Commit(staged)
    if not current(self) or staged ~= self.staged or not self.request or self.request.query ~= self.query then return false end
    self.cached = self.prepared; self.request, self.staged, self.prepared = nil, nil, nil
    return true
end
function Methods:Read() return not self.closed and self.cached and copy(self.cached) or nil end
function Methods:Close() self.closed = true; self.request, self.staged, self.prepared, self.cached = nil, nil, nil, nil end
return Query
