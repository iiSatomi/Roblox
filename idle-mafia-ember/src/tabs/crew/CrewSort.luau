-- Saved CrewAction("sort") contract; exact roster order and pinned slots.
local CrewSort = {}

local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return false end
    for _, field in ipairs({ "session", "account", "place", "release" }) do
        if type(a[field]) ~= "string" or #a[field] == 0
            or a[field] ~= b[field] then return false end
    end
    return true
end

local function equal(a,b)
    if type(a)~=type(b) then return false end
    if type(a)~="table" then return a==b end
    for k,v in pairs(a) do if not equal(v,b[k]) then return false end end
    for k in pairs(b) do if a[k]==nil then return false end end
    return true
end
local function payload(member)
    local result={}
    for _,key in ipairs({"name","rarity","healId","weapon","armor","vehicle","train","atk","def","injuredUntil"}) do
        local v=member[key]
        if v~=nil then
            if type(v)=="string" then if #v>128 then return nil end
            elseif type(v)=="number" then if v~=v or v==math.huge or v==-math.huge then return nil end
            elseif type(v)~="boolean" then return nil end
            result[key]=v
        end
    end
    for _,kind in ipairs({"weapon","armor","vehicle"}) do result[kind.."Bound"]=member[kind.."Bound"]==true end
    return result
end
local function roster(raw)
    local native = type(raw) == "table" and raw.native
    local crew = type(native) == "table" and native.crew
    if type(native) ~= "table" or native.fullSync ~= true
        or type(crew) ~= "table" then return nil end
    local rows, identities, stableIds, count = {}, {}, {}, 0
    for index, member in pairs(crew) do
        if type(index) ~= "number" or index % 1 ~= 0
            or index < 1 or index > 46 or type(member) ~= "table"
            or (index > 1 and (type(member.name) ~= "string"
                or #member.name == 0 or #member.name > 64
                or type(member.rarity) ~= "number"
                or member.rarity ~= member.rarity
                or member.rarity < 0 or member.rarity > 20
                or member.rarity % 1 ~= 0)) then
            return nil
        end
        count = count + 1
        if count > 46 then return nil end
        local key = index == 1 and "PLAYER" or
            #member.name .. ":" .. member.name .. ":" .. member.rarity
        if member.healId~=nil then
            if type(member.healId)~="string" or #member.healId==0 or #member.healId>128 then return nil end
            if stableIds[member.healId] then return nil end
            stableIds[member.healId]=true
            key=key..":"..#member.healId..":"..member.healId
        end
        local data=payload(member)
        if not data then return nil end
        if identities[key] then return nil end
        identities[key] = true
        rows[index] = { key = key,payload=data,
            pinned = index == 1 or member.duty ~= nil
                or member.rolling == true }
    end
    if not rows[1] then return nil end
    return rows, count
end

function CrewSort.read(raw, context)
    if not same(raw, context) or raw.revision ~= context.revision
        or raw.capturedAt ~= context.capturedAt then
        return nil, "Crew sort snapshot changed"
    end
    local rows, count = roster(raw)
    if not rows then return nil, "Current unique Crew roster required" end
    local order, movable = {}, 0
    for index = 1, 46 do
        local row = rows[index]
        if row then
            order[#order + 1] = index .. "=" .. row.key
            if not row.pinned then movable = movable + 1 end
        end
    end
    return { session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        rows = rows, count = count, movable = movable,
        orderKey = table.concat(order, "|") }, nil
end

function CrewSort.propose(view, settings, hash)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing Crew sort input"
    end
    if settings.enabled ~= true then return nil, "Crew sort disabled" end
    if not same(view, view) or type(view.orderKey) ~= "string"
        or type(view.movable) ~= "number" or view.movable < 2 then
        return nil, "Fewer than two available Crew members"
    end
    -- Keep the exact roster in capture; only the deduplication key is compact.
    if type(hash) ~= "function" then return nil, "Crew sort digest unavailable" end
    local ok, digest = pcall(hash, view.orderKey)
    if not ok or type(digest) ~= "string" or #digest ~= 64
        or not digest:match("^[0-9a-fA-F]+$") then
        return nil, "Crew sort digest unavailable"
    end
    return { session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "crewSort",
        actionKey = "crewSort:v2:" .. digest:lower(),
        resources = {}, intent = { kind = "crewSort" } }, nil
end

function CrewSort.capture(proposal, before)
    if type(proposal) ~= "table" or proposal.feature ~= "crewSort"
        or type(proposal.intent) ~= "table"
        or proposal.intent.kind ~= "crewSort"
        or not same(proposal, before)
        or proposal.revision ~= before.revision then
        return nil, "Crew sort baseline changed"
    end
    local rows, count = roster(before)
    if not rows then return nil, "Crew sort baseline unavailable" end
    return { session = proposal.session, account = proposal.account,
        place = proposal.place, release = proposal.release,
        revision = proposal.revision, rows = rows, count = count,serverNow=before.native.serverNow }, nil
end

local function reconcile(proposal,before,after,reply,baseline,restart)
    if type(proposal) ~= "table" or type(reply) ~= "table"
        or not same(proposal,before) or type(after)~="table"
        or (not restart and not same(proposal,after))
        or proposal.account~=after.account or proposal.place~=after.place or proposal.release~=after.release
        or not same(proposal, baseline)
        or proposal.revision ~= baseline.revision
        or before.revision ~= baseline.revision
        or type(after.revision) ~= "number"
        or after.revision~=after.revision or after.revision%1~=0 or after.revision<0 or after.revision==math.huge
        or not (after.session==baseline.session and after.revision>baseline.revision
            or restart and after.session~=baseline.session and type(after.native)=="table"
                and type(baseline.serverNow)=="number" and baseline.serverNow>=0 and baseline.serverNow<math.huge
                and type(after.native.serverNow)=="number" and after.native.serverNow>baseline.serverNow and after.native.serverNow<math.huge)
        or reply.pending==true or reply.code=="rate_limited" or reply.code=="presence" then return "pending" end
    local current, count = roster(after)
    if not current or count ~= baseline.count then return "pending" end
    local oldKeys, newKeys, moved = {}, {}, false
    for index, row in pairs(baseline.rows) do
        oldKeys[row.key] = row
        if current[index] and current[index].pinned ~= row.pinned then
            return "pending"
        end
        if row.pinned and (not current[index]
            or current[index].key ~= row.key) then return "pending" end
        if not current[index] or current[index].key ~= row.key then
            moved = true
        end
    end
    for _, row in pairs(current) do newKeys[row.key] = row end
    for key in pairs(oldKeys) do
        if not newKeys[key] or not equal(oldKeys[key].payload,newKeys[key].payload) then return "pending" end
    end
    if reply.ok == false then return not moved and "rejected" or "pending" end
    if reply.ok == true and type(reply.changed) == "boolean"
        and moved == reply.changed then return "confirmed" end
    return "pending"
end

function CrewSort.evaluate(proposal,before,after,reply,baseline)
    return reconcile(proposal,before,after,reply,baseline,false)
end
function CrewSort.recoverSaved(data,after)
    if type(data)~="table" or type(data.reply)~="table" then return nil end
    local baseline=CrewSort.capture(data.proposal,data.before)
    if not baseline or not equal(baseline,data.baseline) then return nil end
    local outcome=reconcile(data.proposal,data.before,after,data.reply,baseline,true)
    return (outcome=="confirmed" or outcome=="rejected") and outcome or nil
end
return CrewSort
