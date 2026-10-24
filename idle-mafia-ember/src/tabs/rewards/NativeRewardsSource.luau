-- Read-only saved DailyBuff rule plus a separately refreshed Group cache.
local NativeRewardsSource = {}
local Methods = {}
Methods.__index = Methods

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value >= minimum and value < math.huge and value % 1 == 0
end

local function timestamp(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

function NativeRewardsSource.new(rule, lookup, clock,
    release, account, groupId)
    if type(rule) ~= "table"
        or type(rule.isWeekend) ~= "function"
        or type(lookup) ~= "function"
        or type(clock) ~= "table"
        or type(clock.Now) ~= "function"
        or type(release) ~= "string" or #release == 0
        or type(account) ~= "string" or #account == 0
        or not integer(groupId, 1) then
        return nil, "Missing current Rewards sources"
    end
    return setmetatable({ rule = rule, lookup = lookup,
        clock = clock, release = release, account = account,
        groupId = groupId, membership = nil,
        checkedAt = nil, refreshing = false,
        closed = false }, Methods), nil
end

function Methods:IsWeekend(serverNow)
    if self.closed or not integer(serverNow, 0) then return nil end
    local ok, value = pcall(self.rule.isWeekend, serverNow)
    if ok and type(value) == "boolean" then return value end
    return nil
end

function Methods:Refresh(account, groupId)
    if self.closed or self.refreshing
        or account ~= self.account or groupId ~= self.groupId then
        return false
    end
    self.refreshing = true
    local ok, member = pcall(self.lookup, groupId)
    local clockOk, checkedAt = pcall(self.clock.Now, self.clock)
    self.refreshing = false
    if self.closed or not ok or type(member) ~= "boolean"
        or not clockOk or not timestamp(checkedAt) then
        self.membership, self.checkedAt = nil, nil
        return false
    end
    self.membership, self.checkedAt = member, checkedAt
    return true
end

function Methods:Membership(account, groupId)
    if self.closed or account ~= self.account
        or groupId ~= self.groupId
        or type(self.membership) ~= "boolean"
        or not timestamp(self.checkedAt) then
        return nil
    end
    return self.membership, self.checkedAt
end

function Methods:Close()
    self.closed = true
    self.membership, self.checkedAt = nil, nil
end

return NativeRewardsSource
