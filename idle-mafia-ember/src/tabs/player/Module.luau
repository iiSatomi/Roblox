-- Read-only own-player dashboard. Formatting never turns unavailable evidence into zero.
local PlayerTab, Methods = {}, {}
Methods.__index = Methods
local function num(v)
    if type(v) ~= "number" or v ~= v or math.abs(v) > 9007199254740991 then return "Unavailable" end
    local sign = v < 0 and "-" or ""
    local raw = string.format("%.2f", math.abs(v)); local whole, fraction = raw:match("^(%d+)%.(%d+)$")
    if not whole then return "Unavailable" end
    whole = whole:reverse():gsub("(%d%d%d)", "%1,"):reverse():gsub("^,", "")
    fraction = fraction:gsub("0+$", "")
    return sign .. whole .. (#fraction > 0 and "." .. fraction or "")
end
local function cash(v) return type(v) == "number" and "$" .. num(v) or "Unavailable" end
local function hourly(v) return type(v) == "number" and cash(v) .. "/hr" or "Unavailable" end
local function pair(v, max) return num(v) .. " / " .. num(max) end
function PlayerTab.new(section)
    assert(type(section) == "table", "Missing Player section")
    local self = setmetatable({fields = {}, last = {}, propertyRows = {}, powerRows = {}}, Methods)
    local function group(title, open, description)
        local g = section:Group({Text = title, Open = open})
        if description then g:Description({Text = description}) end
        return g
    end
    local function field(g, key, label) self.fields[key] = g:Status({Text = label, Default = "Unavailable"}) end
    local glance = group("Your player", true)
    for _, row in ipairs({{"state", "Data freshness"}, {"identity", "Player"}, {"level", "Level / highest"}, {"prestige", "Prestige"},
        {"attack", "Attack"}, {"defense", "Defense"}, {"health", "Health"}, {"energy", "Energy"}, {"stamina", "Stamina"}}) do field(glance, row[1], row[2]) end
    local income = group("Cash flow", true, "Mugging uses this hub's confirmed payouts since this observation session began. Manual and earlier fights are excluded. Rates include idle time and exclude purchases, losses, and other income. Combined rate adds observed gross mug payouts to the current native property rate.")
    for _, row in ipairs({{"combinedIncome", "Property + mug gross cash/hour"}, {"propertyIncome", "Current property cash/hour"},
        {"mugIncome", "Observed mug payouts/hour"}, {"sample", "Observation window"}, {"mugTotal", "Confirmed session mug payouts"},
        {"mugResults", "Session mugs / wins"}}) do field(income, row[1], row[2]) end
    local wallet = group("Wallet & progress", false)
    for _, row in ipairs({{"cash", "Cash on hand"}, {"bank", "Banked Cash"}, {"tradableGold", "Tradable Gold"}, {"boundGold", "Bound Gold"},
        {"respect", "Respect"}, {"xp", "Experience"}, {"skillPoints", "Unspent skill points"}, {"crew", "Crew size"}, {"family", "Family"},
        {"shield", "Shield remaining"}, {"fightWins", "Lifetime fight wins"}, {"defWins", "Successful defenses"},
        {"operations", "Operations completed"}, {"heists", "Heists / assists completed"}, {"safehouse", "Safehouse level"}}) do field(wallet, row[1], row[2]) end
    self.properties = group("Property portfolio", false, "The native effective rate includes its current fight-income modifier. Per-property rows show active copies and catalog base income; they do not assign shared bonuses to individual buildings.")
    for _, row in ipairs({{"propertyBase", "Income before fight modifiers"}, {"propertyModifier", "Current fight-income multiplier"},
        {"propertyCounts", "Owned / active / inactive copies"}, {"propertyGold", "Native property Gold/day"}}) do field(self.properties, row[1], row[2]) end
    self.power = group("Native power breakdown", false, "Current replicated Attack / Defense components. These totals are not a guarantee about fight rolls.")
    field(self.power, "basePower", "Base Attack / Defense");field(self.power, "gearPower", "Gear Attack / Defense")
    local trust = group("Trust & client-only information", false)
    field(trust, "trust", "Trust score")
    trust:Description({Text = "The update notes mention a trust score. No score field was found in the inspected replicated state or native client sources. Bot-check frequency is not a score. Native challenges remain manual."})
    return self
end
function Methods:Set(key, value)
    if self.last[key] ~= value then self.fields[key]:Set(value, true);self.last[key] = value end
end
function Methods:Render(model)
    local view = type(model) == "table" and model.automationRuntime and model.automationRuntime.playerInfo
    local v = type(view) == "table" and view or {}
    self:Set("state", not view and "Unavailable — waiting for a current player Sync" or v.status == "stale"
        and ("Stale — last Sync " .. num(v.age) .. "s ago") or "Current replicated state")
    self:Set("identity", v.name and ((v.displayName or v.name) .. " (@" .. v.name .. ")") or v.userId and ("User #" .. num(v.userId)) or "Unavailable")
    for _, row in ipairs({{"prestige", "prestige"}, {"attack", "attack"}, {"defense", "defense"}, {"respect", "respect"},
        {"xp", "xp"}, {"skillPoints", "skillPoints"}, {"crew", "crewSize"}, {"fightWins", "fightWins"},
        {"defWins", "defWins"}, {"operations", "opsDone"}, {"safehouse", "safehouse"}}) do self:Set(row[1], num(v[row[2]])) end
    self:Set("level", pair(v.level, v.maxLevel));self:Set("health", pair(v.health, v.maxHealth))
    self:Set("energy", pair(v.energy, v.maxEnergy));self:Set("stamina", pair(v.stamina, v.maxStamina))
    self:Set("cash", cash(v.cash));self:Set("bank", cash(v.banked))
    self:Set("tradableGold", num(v.tradableGold));self:Set("boundGold", num(v.boundGold))
    self:Set("family", v.familyName or "Unavailable");self:Set("shield", v.shieldSeconds and (num(v.shieldSeconds) .. "s") or "Unavailable")
    self:Set("heists", pair(v.heistsDone, v.heistHelps));self:Set("combinedIncome", hourly(v.combinedPerHour))
    self:Set("propertyIncome", hourly(v.propertyPerHour));self:Set("propertyBase", hourly(v.propertyBasePerHour))
    self:Set("propertyModifier", v.propertyMultiplier and (num(v.propertyMultiplier) .. "×") or "Unavailable")
    self:Set("mugIncome", v.mugPerHour ~= nil and hourly(v.mugPerHour) or v.mugStatus or "Unavailable")
    self:Set("sample", v.sampleSeconds and (num(v.sampleSeconds) .. "s observed; 60s minimum") or "Waiting for confirmed history")
    self:Set("mugTotal", cash(v.mugCash));self:Set("mugResults", pair(v.mugFights, v.mugWins))
    self:Set("propertyCounts", num(v.ownedProperties) .. " / " .. num(v.activeProperties) .. " / " .. num(v.inactiveProperties))
    self:Set("propertyGold", num(v.propertyGoldPerDay));self:Set("basePower", pair(v.attackBase, v.defenseBase))
    self:Set("gearPower", pair(v.gearAttack, v.gearDefense));self:Set("trust", v.trustStatus or "Not exposed by the observed client")
    local names = {base = "Base", gear = "Gear", equipment = "Equipment", recruits = "Recruits", crewBonus = "Crew bonus",
        prestigeMult = "Prestige multiplier", skillMult = "Skill multiplier", safehouseMult = "Safehouse multiplier",
        familyBonus = "Family bonus", territoryBonus = "Territory bonus", collection = "Collection", trophies = "Trophies",
        trophyBonus = "Trophy bonus", background = "Background", border = "Border", totalBonus = "Total bonus"}
    local function update(rows, key, group, label, value)
        local record = rows[key]
        if not record then record = {handle = group:Status({Text = label, Default = "Unavailable"})};rows[key] = record end
        if record.value ~= value then record.handle:Set(value, true);record.value = value end
        if not record.visible then record.handle:SetVisible(true);record.visible = true end
        record.seen = true
    end
    for _, rows in ipairs({self.powerRows, self.propertyRows}) do for _, record in pairs(rows) do record.seen = false end end
    for _, row in ipairs(v.powerBreakdown or {}) do
        update(self.powerRows, row.id, self.power, names[row.id] or row.id, pair(row.attack, row.defense))
    end
    for _, row in ipairs(v.properties or {}) do
        update(self.propertyRows, row.id, self.properties, row.name,
            row.name .. " — " .. num(row.active) .. "/" .. num(row.owned) .. " active; " .. hourly(row.activeBasePerHour) .. " base"
                .. (row.activeBaseGoldPerDay and row.activeBaseGoldPerDay > 0 and ("; " .. num(row.activeBaseGoldPerDay) .. " Gold/day base") or ""))
    end
    for _, rows in ipairs({self.powerRows, self.propertyRows}) do
        for _, record in pairs(rows) do
            if not record.seen and record.visible then record.handle:SetVisible(false);record.visible = false end
        end
    end
    return true
end
return PlayerTab
