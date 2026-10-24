-- UTC earned monthly claim view; current native config must enable it.
local MonthlyRewardsState = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value < math.huge and value >= minimum and value % 1 == 0
end

local function calendarDays(year, month)
    local days = { 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 }
    if month == 2 and (year % 4 == 0 and year % 100 ~= 0
        or year % 400 == 0) then return 29 end
    return math.min(days[month], 30)
end

function MonthlyRewardsState.read(raw, context)
    if type(raw) ~= "table" or type(context) ~= "table" then
        return nil, "Missing monthly state or context"
    end
    for _, field in ipairs({ "session", "account", "place", "release",
        "revision", "capturedAt" }) do
        if raw[field] ~= context[field] then
            return nil, "Monthly snapshot header changed"
        end
    end
    local native = raw.native
    if type(native) ~= "table" or native.fullSync ~= true then
        return nil, "Complete monthly Sync required"
    end
    if type(raw.monthlyConfig) ~= "table"
        or raw.monthlyConfig.enabled ~= true then
        return nil, "Native monthly calendar is disabled"
    end
    local now = context.serverNow
    if not integer(now, 0) or native.serverNow ~= now then
        return nil, "Trusted server UTC time required"
    end
    local daySeconds = now % 86400
    if daySeconds < 5 or daySeconds > 86395 then
        return nil, "Monthly claim waits across UTC boundary"
    end
    local utc = os.date("!*t", now)
    local month = os.date("!%Y-%m", now)
    local today = tonumber(os.date("!%Y%j", now))
    local total = calendarDays(utc.year, utc.month)
    local record = native.monthly
    if record ~= nil and (type(record) ~= "table"
        or type(record.month) ~= "string"
        or not record.month:match("^%d%d%d%d%-%d%d$")
        or not integer(record.claimed, 0)
        or (record.lastDay ~= nil and not integer(record.lastDay, 0))) then
        return nil, "Invalid native monthly record"
    end
    local current = record and record.month == month
    local claimed = current and record.claimed or 0
    if claimed >= total then return nil, "Monthly calendar complete" end
    if current and record.lastDay == today then
        return nil, "Monthly reward already claimed today"
    end
    return {
        session = context.session, account = context.account,
        place = context.place, release = context.release,
        revision = context.revision, capturedAt = context.capturedAt,
        month = month, today = today, total = total,
        claimed = claimed, nextDay = claimed + 1,
    }, nil
end

return MonthlyRewardsState
