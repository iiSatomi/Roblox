-- Explicit local metadata review. Never migrates, adopts, reconciles or writes state.
local SavedStateReview = {}
local NOTICE = "Review only; does not authorize activation or clear unknown history."
local MAX_BYTES = 4194304 -- Entire pass, including fresh verification.
local MAX_FILE = 2097152
local MAX_ITEMS = 8192
local legacyNames = { "settings", "configs", "action-journal", "market-flip", "market-sell",
    "market-memory", "property-review", "gear-plan", "high-value-targets", "combat-evidence" }
local journalStates = {sent=true, confirmed=true, rejected=true, unconfirmed=true,
    confirmed_late=true, no_op=true, response_received=true, call_error=true,
    released_unverified=true, interrupted=true}
local terminal = {confirmed=true, rejected=true, confirmed_late=true, no_op=true}
local families = {checkpoint=true, ["release-owner"]=true, profiles=true,
    ["crew-replacement"]=true, ["market-rent"]=true, ["territory-recall"]=true,
    ["player-fights"]=true, payouts=true, ["adapter-unsent"]=true}
local function timestamp(v)
    return type(v) == "number" and v == v and v >= 0 and v <= 9007199254740991
end

local function integer(v, minimum)
    return type(v) == "number" and v == v and v >= (minimum or 0)
        and v <= 9007199254740991 and v % 1 == 0
end
local function count(value)
    if type(value) ~= "table" then return nil end
    local n = 0
    for _ in pairs(value) do n = n + 1; if n > MAX_ITEMS then return nil end end
    return n
end
local function array(value, maximum)
    local n = count(value)
    if not n or n > maximum then return nil end
    for key in pairs(value) do if not integer(key, 1) or key > n then return nil end end
    return n
end
local function safeSegment(value)
    return type(value) == "string" and #value > 0 and #value <= 160
        and value ~= "." and value ~= ".." and value:match("^[%w_.%-]+$") ~= nil
end
local function hash(deps, value)
    local ok, digest = pcall(deps.sha256, value)
    if not ok or type(digest) ~= "string" or #digest ~= 64
        or not digest:match("^[%x]+$") then error("Review digest unavailable", 0) end
    return digest:lower()
end
local function numericFields(value, names)
    local result = {}
    for _, name in ipairs(names) do
        if value[name] ~= nil then
            if not integer(value[name]) then return nil end
            result[#result + 1] = name .. "=" .. string.format("%.0f", value[name])
        end
    end
    return #result > 0 and table.concat(result, ", ") or "no recognized saved counters"
end

-- Fluent Core v17 persists integer days in [-1, 1e12] and counts in [0, 1e9].
-- -1 is its unset-day marker, not negative consumption. Never coerce or clamp files.
local function legacySettingsCounters(value)
    local result = {}
    for _, field in ipairs({"favorUsageDay", "favorUsageCount", "sabotageUsageDay",
        "sabotageUsageCount", "sabotageAttemptDay", "sabotageAttemptCount"}) do
        local saved = value[field]
        if saved ~= nil then
            local day = field:sub(-3) == "Day"
            if not integer(saved, day and -1 or 0) or saved > (day and 1e12 or 1e9) then return nil end
            result[#result + 1] = field .. "=" .. string.format("%.0f", saved)
                .. (day and saved == -1 and " (unset)" or "")
        end
    end
    return #result > 0 and table.concat(result, ", ") or "no recognized saved counters"
end

-- Counts describe stored fields only. Envelope recognition is not content validity,
-- provenance, complete history, a trusted counter, or proof a request was unsent.
local function legacySummary(name, data, identity)
    if type(data) ~= "table" then return "Malformed JSON record" end
    local version = data.version
    local expected = name == "settings" and 17 or name == "mugs" and 2 or 1
    if version ~= expected and not (name == "property-review" and version == 2) then
        return "Unsupported schema; contents unknown"
    end
    local prefix = "Recognized v" .. version .. " envelope; "
    if name == "settings" then
        local n = count(data)
        local counters = legacySettingsCounters(data)
        if not n or not counters then return "Malformed preferences or saved counters" end
        return prefix .. (n - 1) .. " saved fields; " .. counters .. "; values not imported or validated"
    elseif name == "configs" then
        local n = count(data.profiles)
        if not n then return "Malformed profile collection" end
        for key, profile in pairs(data.profiles) do
            if type(key) ~= "string" or type(profile) ~= "table"
                or type(profile.settings) ~= "table" or type(profile.enabled) ~= "table" then
                return "Malformed profile row; no rows discarded"
            end
        end
        for _, key in ipairs({"autoload", "nextLoad"}) do
            if data[key] ~= nil and (type(data[key]) ~= "string" or data.profiles[data[key]] == nil) then
                return "Malformed profile selection"
            end
        end
        return prefix .. n .. " profiles; autoload " .. (data.autoload ~= nil and "present" or "absent")
            .. "; next launch " .. (data.nextLoad ~= nil and "present" or "absent") .. "; choices unvalidated"
    elseif name == "action-journal" then
        local n = array(data.entries, 100)
        if not n or not integer(data.nextId, 1) then return "Malformed journal; history unknown" end
        local previous, unresolved, states = 0, 0, {}
        for _, row in ipairs(data.entries) do
            if type(row) ~= "table" or not integer(row.id, 1) or row.id <= previous
                or type(row.feature) ~= "string" or type(row.remote) ~= "string"
                or type(row.identity) ~= "string" or not journalStates[row.state]
                or type(row.at) ~= "number" or row.at ~= row.at or math.abs(row.at) == math.huge
                or row.details ~= nil and type(row.details) ~= "string"
                or row.finishedAt ~= nil and not timestamp(row.finishedAt)
                or row.retryAt ~= nil and not timestamp(row.retryAt) then
                return "Malformed journal row; history unknown; no rows discarded"
            end
            previous = row.id
            states[row.state] = (states[row.state] or 0) + 1
            if not terminal[row.state] then unresolved = unresolved + 1 end
        end
        if data.nextId <= previous then return "Malformed journal nextId; history unknown" end
        local stateCounts = {}
        for state, total in pairs(states) do stateCounts[#stateCounts + 1] = state .. "=" .. total end
        table.sort(stateCounts)
        return prefix .. n .. " retained / 100 maximum; nextId=" .. string.format("%.0f", data.nextId)
            .. "; " .. unresolved .. " rows need review (response_received is not settled success); "
            .. table.concat(stateCounts, ", ") .. "; older history unknown even when all retained rows are terminal"
    end
    local scoped = name == "market-flip" or name == "market-sell" or name == "market-memory"
        or name == "property-review" or name == "gear-plan"
    if scoped and (data.account ~= identity.account or tostring(data.placeId) ~= identity.place) then
        return "Malformed or mismatched original account/place scope"
    end
    if name == "market-flip" or name == "market-sell" then
        local field = name == "market-flip" and "spent" or "listed"
        if not integer(data[field]) or data.tx ~= nil and type(data.tx) ~= "table"
            or data.review ~= nil and type(data.review) ~= "string" then return "Malformed transaction record" end
        return prefix .. field .. "=" .. string.format("%.0f", data[field])
            .. "; transaction " .. (data.tx ~= nil and "present" or "absent")
            .. "; review marker " .. (data.review ~= nil and "present" or "absent")
            .. "; custody and historical usage unknown"
    elseif name == "property-review" then
        if data.state ~= "pending" and data.state ~= "clear" then return "Malformed property marker" end
        return prefix .. "saved marker=" .. data.state .. "; ownership and history unverified"
    elseif name == "gear-plan" then
        if type(data.state) ~= "string" or type(data.pending) ~= "boolean"
            or data.plan ~= nil and type(data.plan) ~= "table" then return "Malformed gear record" end
        return prefix .. "plan " .. (data.plan ~= nil and "present" or "absent")
            .. "; pending=" .. tostring(data.pending) .. "; custody unknown"
    end
    local fields = name == "market-memory" and {"buys", "listings", "trades", "collects"}
        or name == "high-value-targets" and {"targets"}
        or name == "combat-evidence" and {"byId"}
        or name == "mugs" and {"players"} or nil
    if not fields then return "Unsupported envelope" end
    local result = {}
    for _, field in ipairs(fields) do
        local n = count(data[field])
        if not n then return "Malformed collection; no rows discarded" end
        for _, row in pairs(data[field]) do
            if type(row) ~= "table" then return "Malformed collection row; no rows discarded" end
        end
        result[#result + 1] = n .. " " .. field
    end
    if data.scouts ~= nil then
        local n = count(data.scouts)
        if not n then return "Malformed scout collection" end
        result[#result + 1] = n .. " scouts"
    end
    return prefix .. table.concat(result, "; ") .. "; contents and provenance unvalidated"
end

local function takeScope(body)
    if type(body) ~= "string" then return nil end
    local length, remainder = body:match("^(%d+):(.*)$")
    length = tonumber(length)
    if not length or length < 1 or length > 200 or string.len(remainder) < length then return nil end
    return remainder:sub(1, length), remainder:sub(length + 1)
end
local function checkpointSummary(key, data, identity, deps)
    local family, body = key:match("^idle%-mafia%-ember:([%w%-]+):v%d+:(.*)$")
    local scope, suffix
    if not families[family] then return "Unknown checkpoint family/scope; contents unvalidated" end
    if family == "adapter-unsent" then
        -- Its producer key contains a digest, not a length-prefixed account.
        if type(data.account) ~= "string" or type(data.place) ~= "string"
            or type(data.release) ~= "string" or data.version ~= 1 then
            return "Unknown adapter receipt scope/envelope"
        end
        scope = {account=data.account, place=data.place, release=data.release}
    elseif family == "crew-replacement" then
        scope = type(data) == "table" and data.scope
        if type(scope) ~= "table" or type(scope.account) ~= "string" or type(scope.place) ~= "string"
            or type(scope.release) ~= "string" or type(scope.ownerId) ~= "string"
            or data.schema ~= 1 or not integer(data.generation, 1) then
            return "Unknown checkpoint scope; Crew envelope malformed"
        end
        local expected = "idle-mafia-ember:crew-replacement:v1:" .. scope.account .. ":" .. scope.place .. ":" .. scope.release
        if key ~= expected and key ~= expected .. ":adapter-unsent:" .. string.format("%.0f", data.generation) then
            return "Unknown checkpoint scope; Crew key/envelope mismatch"
        end
        if key == expected and type(data.usage) ~= "table" then return "Malformed Crew usage envelope" end
    elseif family then
        local account, rest = takeScope(body)
        local place, remaining
        if rest then place, remaining = takeScope(rest) end
        if not account or not place then return "Unknown checkpoint scope; malformed scoped key" end
        local release
        if family ~= "release-owner" and family ~= "profiles" then
            release, suffix = takeScope(remaining)
            if not release or suffix ~= "" and suffix:sub(1,1) ~= ":" then
                return "Unknown checkpoint release; malformed scoped key"
            end
        end
        scope = {account=account, place=place, release=release or data.release}
        if data.account ~= nil and data.account ~= account or data.place ~= nil and data.place ~= place
            or release ~= nil and data.release ~= nil and data.release ~= release then
            return "Unknown checkpoint scope; key/envelope mismatch"
        end
    else
        return "Unknown checkpoint family/scope; contents unvalidated"
    end
    if scope.account ~= identity.account or scope.place ~= identity.place then return nil end
    local release = type(scope.release) == "string" and scope.release or nil
    local original = release and (release == identity.release and "current release" or "other release")
        .. "; release SHA256=" .. hash(deps, release) or "release unknown or unscoped"
    local usage = type(data.usage) == "table" and numericFields(data.usage,
        {"attempted", "spent", "used", "confirmed", "count", "total"}) or nil
    local known = family == "crew-replacement" and data.schema == 1
        or family == "release-owner" and data.version == 1
    local retained = data.records ~= nil and array(data.records, MAX_ITEMS) or nil
    if data.records ~= nil and not retained then return "Malformed checkpoint records; no rows discarded" end
    local saved = {}
    for _, name in ipairs({"favorUsage", "sabotageUsage", "bossUsage", "globalClaimUsage", "globalAttackUsage",
        "familyClaimUsage", "familyAttackUsage", "bossShopUsage", "familyContributionUsage", "eventShopUsage",
        "crewHireUsage", "marketRentUsage", "playerFightUsage", "chestUsage"}) do
        if data[name] ~= nil then
            local fields = type(data[name]) == "table" and numericFields(data[name],
                {"day", "count", "attempts", "attempted", "spent", "hits", "used", "total"}) or nil
            saved[#saved + 1] = name .. ": " .. (fields or "malformed/unknown")
        end
    end
    local scalar = numericFields(data, {"requestHighwater", "lastRequestId", "residencyAttempts", "stationAttempts", "prestigeAttempts"})
    return (known and "Recognized " or "Unvalidated ") .. family .. " envelope; current account/place; " .. original
        .. "; custody fields " .. ((data.active ~= nil or data.pending ~= nil or data.tx ~= nil or data.transaction ~= nil or retained and retained > 0) and "present" or "absent")
        .. "; retained records " .. (retained ~= nil and tostring(retained) or "unknown/not applicable")
        .. "; saved usage " .. (usage or "unknown") .. "; " .. (scalar or "malformed counters")
        .. (#saved > 0 and ("; " .. table.concat(saved, "; ")) or "")
        .. "; content validity and historical consumption unknown"
end

function SavedStateReview.new(deps)
    if type(deps) ~= "table" or type(deps.identity) ~= "table"
        or not safeSegment(deps.identity.account) or not safeSegment(deps.identity.place)
        or type(deps.identity.release) ~= "string" or #deps.identity.release == 0 or #deps.identity.release > 160
        or type(deps.directory) ~= "string" or #deps.directory > 160
        or type(deps.ExecutorStorageAdapter) ~= "table" or type(deps.ExecutorStorageAdapter.new) ~= "function"
        or type(deps.RedundantStore) ~= "table" or type(deps.RedundantStore.new) ~= "function"
        or type(deps.httpService) ~= "table" and type(deps.httpService) ~= "userdata"
        or type(deps.sha256) ~= "function" then return nil, "Read-only review dependencies unavailable" end
    for part in deps.directory:gmatch("[^/]+") do
        if not safeSegment(part) then return nil, "Review directory unavailable" end
    end
    if deps.directory == "" or deps.directory:sub(1, 1) == "/" or deps.directory:find("//", 1, true)
        or deps.directory:find("\\", 1, true) then return nil, "Review directory unavailable" end
    local env = deps.executorEnv
    -- TestEntry may use a memory cache fallback. Never mistake it for account files.
    local api = type(env) == "table" and (env.savedStateReadApi or env) or nil
    if type(api) ~= "table" or type(api.isfile) ~= "function" or type(api.readfile) ~= "function"
        or type(api.listfiles) ~= "function" then return nil, "Read-only file/listing capabilities unavailable; history unknown" end
    local function reject() error("Read-only review cannot mutate storage", 0) end
    local adapter, reason = deps.ExecutorStorageAdapter.new({
        isfolder=function() return false end, makefolder=reject, writefile=reject,
        isfile=api.isfile, readfile=api.readfile, listfiles=api.listfiles,
        jsonEncode=function(value) return deps.httpService:JSONEncode(value) end,
        jsonDecode=function(value) return deps.httpService:JSONDecode(value) end,
        hash=deps.sha256,
    })
    if not adapter then return nil, reason end
    local identity = {account=deps.identity.account, place=deps.identity.place, release=deps.identity.release}
    local directory = deps.directory .. "/checkpoints"
    local reader = {}
    function reader:Read(current)
        local report = {notice=NOTICE, completeHistory=false, authorizesActivation=false,
            rows={}, rechecked=false, bytesRead=0, unknown=true}
        local cache, order, exhausted, failures = {}, {}, false, false
        local function check()
            if type(current) ~= "function" or current() ~= true then error("Review closed", 0) end
        end
        local function fresh(path)
            check()
            if exhausted then error("Review byte budget exhausted", 0) end
            local ok, bytes = pcall(adapter.files.ReadFile, adapter.files, path)
            check()
            if not ok then failures=true;error("Review file unreadable", 0) end
            if bytes ~= nil then
                if type(bytes) ~= "string" then failures=true;error("Review file unreadable", 0) end
                report.bytesRead = report.bytesRead + #bytes
                if #bytes > MAX_FILE or report.bytesRead > MAX_BYTES then
                    exhausted, failures = true, true
                    error("Review file or aggregate byte limit exceeded", 0)
                end
            end
            return bytes
        end
        local files = {WriteFile=reject}
        function files:ReadFile(path)
            check()
            if cache[path] then
                if cache[path].failed then error("Review file unavailable", 0) end
                return cache[path].bytes
            end
            local ok, bytes = pcall(fresh, path)
            cache[path] = ok and {bytes=bytes} or {failed=true}
            order[#order + 1] = path
            if not ok then error("Review file unavailable", 0) end
            return bytes
        end
        local listed
        function files:ListFiles(path)
            check()
            local ok, paths = pcall(adapter.files.ListFiles, adapter.files, path)
            check()
            if not ok or type(paths) ~= "table" then failures=true;return nil end
            listed = {}
            for index, value in ipairs(paths) do listed[index] = value end
            return paths
        end
        local function row(label, summary, digest)
            report.rows[#report.rows + 1] = {label=label, summary=summary, digest=digest}
        end
        local legacyRoot = "IdleMafiaFluent/" .. identity.place .. "/" .. identity.account .. "/"
        local paths = {}
        for _, name in ipairs(legacyNames) do paths[#paths + 1] = {name=name, label=name, path=legacyRoot .. name .. ".json"} end
        paths[#paths + 1] = {name="configs", label="configs backup", path=legacyRoot .. "configs.json.bak"}
        paths[#paths + 1] = {name="mugs", label="mug history", path="IdleMafiaMugTracker/" .. identity.account .. "/mugs.json"}
        for _, item in ipairs(paths) do
            check()
            local read, bytes = pcall(files.ReadFile, files, item.path)
            check()
            if not read then row(item.label, "Unknown: read failed or review size limit reached")
            elseif bytes == nil then row(item.label, "Not observed at this known path; historical absence unproven")
            else
                local decoded, data = pcall(adapter.codec.Decode, adapter.codec, bytes)
                check()
                local ok, digest = pcall(hash, deps, bytes)
                if not ok then failures=true end
                row(item.label, decoded and legacySummary(item.name, data, identity) or "Malformed JSON; contents unknown",
                    ok and digest or "unavailable")
            end
        end
        local store = deps.RedundantStore.new(files, adapter.codec, adapter.sha256, directory, {strictRecovery=true})
        local discovered, keys = pcall(store.ListKeys, store)
        check()
        if not discovered or type(keys) ~= "table" then
            failures=true
            row("Ember checkpoints", "Unknown: strict discovery failed, malformed slot, digest, listing or byte limit")
            -- Preserve useful partial observations when strict discovery stops at damage.
            -- Never recover a damaged pair or promote a readable older slot to authority.
            for index, path in ipairs(listed or {}) do
                check()
                local name = path:sub(#directory + 2)
                local id = name:match("^([%da-f]+)%.[ab]%.json$")
                if id and #id == 64 then
                    local read, bytes = pcall(files.ReadFile, files, path)
                    local summary, include = "Unknown: slot unreadable or size budget exhausted", true
                    local proof
                    if read and bytes ~= nil then
                        proof = hash(deps, bytes)
                        summary = "Unknown: malformed or unrecoverable strict slot"
                        local decoded, envelope = pcall(adapter.codec.Decode, adapter.codec, bytes)
                        if decoded and type(envelope) == "table" and type(envelope.key) == "string" then
                            local okPaths, first, second = pcall(store.Paths, store, envelope.key)
                            if okPaths and (path == first or path == second) then
                                local valid, value = pcall(store.Read, store, envelope.key)
                                if valid and type(value) == "table" then
                                    summary = checkpointSummary(envelope.key, value, identity, deps)
                                    include = summary ~= nil
                                end
                            end
                        end
                    end
                    if include then
                        row("Observed checkpoint slot " .. index,
                            (summary or "Unknown") .. "; slot SHA256=" .. id, proof)
                    end
                end
            end
        else
            local relevant, other = 0, 0
            for _, key in ipairs(keys) do
                check()
                local read, value = pcall(store.Read, store, key)
                if not read or type(value) ~= "table" then failures=true;row("Ember checkpoint", "Unknown: strict read failed")
                else
                    local summary = checkpointSummary(key, value, identity, deps)
                    if summary then
                        relevant = relevant + 1
                        local first, second = store:Paths(key)
                        local proofs = {}
                        for _, path in ipairs({first, second}) do
                            local saved = cache[path]
                            if saved and saved.bytes then proofs[#proofs + 1] = hash(deps, saved.bytes) end
                        end
                        row("Ember checkpoint " .. relevant, summary .. "; key SHA256=" .. hash(deps, key), table.concat(proofs, ", "))
                    else other = other + 1 end
                end
            end
            row("Ember discovery", relevant .. " relevant or unknown-scope records; " .. other
                .. " other-account/place records withheld; absent records do not establish complete history")
        end
        local matched = not failures
        for _, path in ipairs(order) do
            check()
            local previous = cache[path]
            if previous.failed then matched=false
            else
                local ok, bytes = pcall(fresh, path)
                if not ok or bytes ~= previous.bytes then matched=false end
            end
        end
        if listed then
            check()
            local ok, again = pcall(adapter.files.ListFiles, adapter.files, directory)
            check()
            if not ok or type(again) ~= "table" or #again ~= #listed then matched=false
            else
                table.sort(listed);table.sort(again)
                for index, value in ipairs(listed) do if again[index] ~= value then matched=false end end
            end
        else matched=false end
        report.rechecked = matched
        report.status = matched and "Observed bytes/listing rechecked; sequential reads are not an atomic snapshot"
            or "Unknown: source changed, unreadable, malformed or review limits reached; observed rows may be stale"
        check()
        return report
    end
    return reader, nil
end

return SavedStateReview
