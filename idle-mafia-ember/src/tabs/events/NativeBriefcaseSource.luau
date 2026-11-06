-- Read native seasonal attributes/rules and the actual free board; never spends keys.
local NativeBriefcaseSource = {}
local MAX = 9007199254740991
local fields = {"session", "account", "place", "release", "revision", "capturedAt"}
local function integer(v, low)
    return type(v) == "number" and v == v and v >= low and v <= MAX and v % 1 == 0
end
local function number(v)
    return type(v) == "number" and v == v and v >= 0 and v <= MAX
end
local function copy(v)
    if type(v) ~= "table" then return v end
    local out = {}; for k, child in pairs(v) do out[k] = copy(child) end; return out
end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for k, v in pairs(a) do if not equal(v, b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end
local function board(raw)
    local b = type(raw) == "table" and raw.board
    if type(b) ~= "table" or not integer(raw.season, 1) or not integer(raw.free, 0)
        or not integer(b.n, 1) or not integer(b.cfg, 0) or type(b.opened) ~= "table" then return nil end
    local opened, count = {}, 0
    for key, row in pairs(b.opened) do
        count = count + 1
        local index = type(key) == "string" and tonumber(key:match("^c(%d+)$"))
        if count > 12 or not integer(index, 1) or index > 12 or key ~= "c" .. index
            or type(row) ~= "table" or type(row.p) ~= "string" or #row.p < 1 or #row.p > 120
            or row.p:find("[%c]") then return nil end
        opened[key] = {p = row.p}
    end
    return {season = raw.season, free = raw.free, board = {n = b.n, cfg = b.cfg, opened = opened}}
end
local function header(raw, release)
    if type(raw) ~= "table" or raw.release ~= release or type(raw.native) ~= "table"
        or raw.native.fullSync ~= true or not number(raw.native.serverNow)
        or not integer(raw.revision, 0) or not number(raw.capturedAt) then return nil end
    local out = {}
    for _, field in ipairs(fields) do out[field] = raw[field] end
    for _, field in ipairs({"session", "account", "place", "release"}) do
        if type(out[field]) ~= "string" or #out[field] < 1 or #out[field] > 200 then return nil end
    end
    return out
end
function NativeBriefcaseSource.new(rules, readCurrent, fingerprint, release, stateReader)
    if type(rules) ~= "table" or rules.CASES ~= 12 or not integer(rules.VERSION, 0)
        or type(readCurrent) ~= "function" or type(fingerprint) ~= "string" or #fingerprint ~= 64
        or not fingerprint:match("^[%x]+$") or type(release) ~= "string" or #release < 1 or #release > 200
        or type(stateReader) ~= "table" or type(stateReader.read) ~= "function" then
        return nil, "Reviewed native Briefcase source required"
    end
    local closed, generation, latest = false, 0, nil
    local source = {sourceKey = fingerprint:lower(), release = release}
    local function observe()
        if closed or rules.CASES ~= 12 or not integer(rules.VERSION, 0) then return nil end
        local version = rules.VERSION
        local ok, current = pcall(readCurrent)
        if not ok or type(current) ~= "table" or closed or rules.CASES ~= 12
            or rules.VERSION ~= version or not number(current.serverNow) then return nil end
        -- This is BriefcasesTab's tonumber(attribute) or 0 convention.
        local endsAt, season = tonumber(current.GlobalCaseEnd) or 0, tonumber(current.GlobalCaseSeason) or 0
        if not integer(endsAt, 0) or not integer(season, 0) then return nil end
        return {season = season, endAt = endsAt, version = version, observedNow = current.serverNow,
            active = endsAt > current.serverNow, board = board(current.briefcase)}
    end
    local function current(proof)
        local observed = observe()
        return observed ~= nil and proof == latest and observed.season == proof.season
            and observed.endAt == proof.endAt and observed.version == proof.version
            and observed.observedNow >= proof.observedNow and observed.active == proof.active
            and equal(observed.board, proof.board), observed
    end
    function source:Enrich(raw)
        generation, latest = generation + 1, nil
        local bound, observed = header(raw, release), observe()
        if not bound or not observed or (raw.catalogKey ~= nil and raw.catalogKey ~= self.sourceKey) then
            return nil, "Current native Briefcase full Sync and rules required"
        end
        if observed.active and (not observed.board or not equal(board(raw.native.briefcase), observed.board)) then
            return nil, "Current native Briefcase board differs from full Sync"
        end
        observed.header, observed.sourceKey, observed.sourceGeneration = bound, self.sourceKey, generation
        latest = observed
        local enriched = {}; for k, v in pairs(raw) do enriched[k] = v end
        enriched.catalogKey = self.sourceKey
        enriched.briefcaseRules = {cases = 12, version = observed.version}
        enriched.caseEvent = {season = observed.season, endAt = observed.endAt}
        enriched.briefcaseProof = copy(observed)
        return enriched, nil
    end
    source.read = function(raw, context)
        local bound = header(raw, release)
        local contextHeader = {}
        if type(context) == "table" then for _, k in ipairs(fields) do contextHeader[k] = context[k] end end
        if not bound or not latest or not equal(bound, contextHeader) or not equal(bound, latest.header)
            or not equal(raw.briefcaseProof, latest) or not current(latest) then
            return nil, "Briefcase proof is not from this current native source"
        end
        if not latest.active then return nil, "Briefcase event is inactive" end
        if latest.endAt - math.max(raw.native.serverNow, latest.observedNow) <= 5 then
            return nil, "Briefcase event is ending"
        end
        local view, reason = stateReader.read(raw, context)
        if view then view.sourceGeneration, view.sourceKey = latest.sourceGeneration, source.sourceKey end
        return view, reason
    end
    function source:CanDispatch(proposal)
        local i = type(proposal) == "table" and proposal.intent
        if closed or not latest or type(i) ~= "table" or proposal.feature ~= "briefcases"
            or proposal.release ~= release or proposal.revision ~= latest.header.revision
            or i.kind ~= "freeBriefcasePick" or i.command ~= "open" or not integer(i.index, 1) or i.index > 12
            or i.sourceKey ~= self.sourceKey or i.catalogKey ~= self.sourceKey
            or i.sourceGeneration ~= latest.sourceGeneration or i.season ~= latest.season
            or i.endAt ~= latest.endAt or not latest.active or not latest.board
            or i.board ~= latest.board.board.n or i.free ~= latest.board.free or i.free < 1
            or latest.board.season ~= i.season or latest.board.board.cfg ~= latest.version
            or latest.board.board.opened["c" .. i.index] ~= nil then return false end
        for _, k in ipairs({"session", "account", "place", "release"}) do
            if proposal[k] ~= latest.header[k] then return false end
        end
        local valid, observed = current(latest)
        return valid and observed.active and observed.endAt - observed.observedNow > 5
    end
    function source:Close() closed, latest = true, nil end
    return source, nil
end
return NativeBriefcaseSource
