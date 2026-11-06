-- Read-only current player facts and observed confirmed mug payouts; no RPC or balance-delta attribution.
local PlayerInfo, Methods = {}, {}
Methods.__index = Methods
local MAX = 9007199254740991
local scope = {"session", "account", "place", "release"}
local function number(v) return type(v) == "number" and v == v and v >= 0 and v <= MAX end
local function integer(v) return number(v) and v % 1 == 0 end
local function text(v) return type(v) == "string" and #v > 0 and #v <= 120 and not v:find("[%c]") end
local function clone(v)
    if type(v) ~= "table" then return v end
    local out = {}; for k, child in pairs(v) do out[k] = clone(child) end; return out
end
local function dense(t, max)
    if type(t) ~= "table" or #t > max then return false end
    local n = 0
    for k in pairs(t) do if not integer(k) or k < 1 or k > #t then return false end; n = n + 1 end
    return n == #t
end
function PlayerInfo.new(identity)
    assert(type(identity) == "table", "Missing player information scope")
    local own = {}
    for _, k in ipairs(scope) do assert(text(identity[k]), "Invalid player information scope"); own[k] = identity[k] end
    return setmetatable({identity = own}, Methods)
end
local function properties(native, facts, out)
    if type(native.properties) ~= "table" then return end
    local owned, total = {}, 0
    for id, row in pairs(native.properties) do
        if not text(id) or type(row) ~= "table" or not integer(row.owned) or row.owned > 1000 then return end
        owned[id], total = row.owned, total + row.owned
    end
    out.ownedProperties = total
    if not dense(native.lots, 1000) then return end
    local active, count = {}, 0
    for _, id in ipairs(native.lots) do
        if id ~= "" then
            if not text(id) or not owned[id] then return end
            active[id], count = (active[id] or 0) + 1, count + 1
            if active[id] > owned[id] then return end
        end
    end
    out.activeProperties, out.inactiveProperties = count, total - count
    if not facts or not dense(facts.properties, 256) then return end
    local rows, seen = {}, {}
    for _, row in ipairs(facts.properties) do
        if type(row) ~= "table" or not text(row.id) or seen[row.id] or not text(row.name)
            or not number(row.incomePerHour) then return end
        seen[row.id] = true
        if (owned[row.id] or 0) > 0 then
            rows[#rows + 1] = {id = row.id, name = row.name, owned = owned[row.id], active = active[row.id] or 0,
                basePerHour = row.incomePerHour, activeBasePerHour = row.incomePerHour * (active[row.id] or 0),
                activeBaseGoldPerDay = number(row.goldPerDay) and row.goldPerDay * (active[row.id] or 0) or nil}
        end
    end
    for id, n in pairs(owned) do if n > 0 and not seen[id] then return end end
    out.properties = rows
end
local function sample(self, ledger, now, out)
    out.mugStatus = "Confirmed fight history unavailable"
    if type(ledger) ~= "table" or not integer(ledger.fights) or not integer(ledger.lastRequestId)
        or not dense(ledger.recent, 32) then return end
    if not self.sample then
        self.sample = {start = now, high = ledger.lastRequestId, total = ledger.fights, cash = 0, fights = 0, wins = 0, complete = true}
    end
    local s = self.sample
    if ledger.fights < s.total or ledger.lastRequestId < s.high then s.complete = false end
    local rows, high = {}, 0
    for _, row in ipairs(ledger.recent) do
        if type(row) ~= "table" or not integer(row.requestId) or row.requestId <= high
            or (row.feature ~= "combat" and row.feature ~= "warCombat") or type(row.receipt) ~= "table"
            or not number(row.receipt.cashConfirmed) or type(row.receipt.won) ~= "boolean" then s.complete = false; break end
        high = row.requestId
        if row.requestId > s.high then rows[#rows + 1] = row end
    end
    if #rows ~= ledger.fights - s.total then s.complete = false end
    if s.complete then
        for _, row in ipairs(rows) do
            if row.feature == "combat" then
                s.cash, s.fights = s.cash + row.receipt.cashConfirmed, s.fights + 1
                s.wins = s.wins + (row.receipt.won and 1 or 0)
            end
        end
    end
    s.high, s.total = ledger.lastRequestId, ledger.fights
    out.sampleSeconds = now - s.start
    out.mugCash, out.mugFights, out.mugWins = s.cash, s.fights, s.wins
    if not s.complete then out.mugStatus = "Incomplete confirmed history; hourly rate unavailable"; return end
    if out.sampleSeconds < 60 then out.mugStatus = "Collecting a 60-second observed sample"; return end
    local rate = s.cash * 3600 / out.sampleSeconds
    if not number(rate) then out.mugStatus = "Hourly rate unavailable"; return end
    out.mugPerHour, out.mugStatus = rate, "Observed session gross payouts; includes idle time"
    if out.propertyPerHour and number(rate + out.propertyPerHour) then out.combinedPerHour = rate + out.propertyPerHour end
end
function Methods:Observe(raw, now, facts, ledger)
    if self.closed or self.retired or type(raw) ~= "table" or not number(now) or not number(raw.capturedAt)
        or raw.capturedAt > now or now - raw.capturedAt > 2 or not integer(raw.revision)
        or self.lastNow and now < self.lastNow or type(raw.native) ~= "table" or raw.native.fullSync ~= true then return nil end
    for _, k in ipairs(scope) do if raw[k] ~= self.identity[k] then self.retired = true; self.view, self.sample = nil, nil; return nil end end
    local n = raw.native
    if not number(n.serverNow) then return nil end
    if self.nativeUserId and n.userId ~= self.nativeUserId then
        self.retired = true; self.view, self.sample = nil, nil; return nil
    end
    if integer(n.userId) then self.nativeUserId = n.userId end
    if type(facts) ~= "table" or not integer(facts.userId) or facts.userId ~= n.userId then facts = nil end
    local out = {status = "current", capturedAt = raw.capturedAt, serverNow = n.serverNow,
        userId = integer(n.userId) and n.userId or nil, trustStatus = "Not exposed by the observed client"}
    if facts then out.name = text(facts.name) and facts.name or nil; out.displayName = text(facts.displayName) and facts.displayName or nil end
    for _, k in ipairs({"level", "maxLevel", "prestige", "respect", "xp", "skillPoints", "cash", "banked", "crewSize",
        "fightWins", "defWins", "heistsDone", "heistHelps", "opsDone", "safehouse"}) do out[k] = number(n[k]) and n[k] or nil end
    local stats, derived, pools = n.stats or {}, n.derived or {}, n.pools or {}
    if type(stats) ~= "table" or type(derived) ~= "table" or type(pools) ~= "table" then return nil end
    out.attackBase, out.defenseBase = number(stats.atkBase) and stats.atkBase or nil, number(stats.defBase) and stats.defBase or nil
    out.gearAttack, out.gearDefense = number(derived.gearAtk) and derived.gearAtk or nil, number(derived.gearDef) and derived.gearDef or nil
    local breakdown = derived.statBreakdown
    if type(breakdown) == "table" then
        for _, row in ipairs({{"atk", "attack"}, {"def", "defense"}}) do
            local b = breakdown[row[1]]
            if type(b) == "table" and number(b.total) then out[row[2]] = b.total end
        end
    end
    if type(breakdown) == "table" then
        out.powerBreakdown = {}
        for _, key in ipairs({"base", "gear", "equipment", "recruits", "crewBonus", "prestigeMult", "skillMult",
            "safehouseMult", "familyBonus", "territoryBonus", "collection", "trophies", "trophyBonus", "background", "border", "totalBonus"}) do
            local row = {id = key}
            for _, pair in ipairs({{"atk", "attack"}, {"def", "defense"}}) do
                local b = breakdown[pair[1]]; local v = type(b) == "table" and b[key]
                if type(v) == "number" and v == v and v >= -MAX and v <= MAX then row[pair[2]] = v end
            end
            if row.attack ~= nil or row.defense ~= nil then out.powerBreakdown[#out.powerBreakdown + 1] = row end
        end
    end
    for _, k in ipairs({"health", "energy", "stamina"}) do out[k] = number(pools[k]) and pools[k] or nil end
    for _, row in ipairs({{"maxHealth", "effMaxHealth"}, {"maxEnergy", "effMaxEnergy"}, {"maxStamina", "effMaxStamina"}}) do
        local v = derived[row[2]]; if v == nil then v = stats[row[1]] end
        out[row[1]] = number(v) and v or nil
    end
    out.familyName = text(derived.familyName) and derived.familyName or nil
    out.shieldSeconds = number(n.shieldUntil) and math.max(0, n.shieldUntil - n.serverNow) or nil
    out.propertyBasePerHour = number(derived.incomePerHour) and derived.incomePerHour or nil
    out.propertyGoldPerDay = number(derived.goldPerDay) and derived.goldPerDay or nil
    if facts and number(facts.propertyMultiplier) then
        out.propertyMultiplier = facts.propertyMultiplier
        local rate = out.propertyBasePerHour and out.propertyBasePerHour * facts.propertyMultiplier
        out.propertyPerHour = number(rate) and rate or nil
    end
    for _, row in ipairs({{"inventory", "tradableGold"}, {"inventoryBound", "boundGold"}}) do
        local inv = n[row[1]]
        if type(inv) == "table" and (inv.gold_bar == nil or integer(inv.gold_bar)) then out[row[2]] = inv.gold_bar or 0 end
    end
    properties(n, facts, out)
    sample(self, ledger, now, out)
    self.view, self.lastNow = clone(out), now
    return out
end
function Methods:Read(now)
    if self.closed or self.retired or not self.view or not number(now) or now < self.lastNow then return nil end
    local out = clone(self.view); out.age = now - out.capturedAt
    if out.age > 2 then out.status = "stale"; out.mugPerHour, out.combinedPerHour = nil, nil end
    return out
end
function Methods:Close() self.closed = true; self.view, self.sample = nil, nil end
return PlayerInfo
