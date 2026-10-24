-- Injected quarter-second tick owner; host supplies an asynchronous timer.
local RuntimeLoop = {}
local Methods = {}
Methods.__index = Methods

function RuntimeLoop.new(driver, scheduler, period)
    assert(type(driver) == "table" and type(driver.Tick) == "function"
        and type(driver.Close) == "function"
        and type(scheduler) == "table"
        and type(scheduler.After) == "function"
        and type(scheduler.Cancel) == "function",
        "Missing runtime loop dependencies")
    local interval = period or 0.25
    assert(type(interval) == "number" and interval >= 0.25
        and interval <= 5 and interval == interval,
        "Invalid runtime tick interval")
    return setmetatable({ driver = driver, scheduler = scheduler,
        period = interval, alive = false, handle = nil }, Methods)
end

function Methods:Schedule()
    if not self.alive then return end
    local handle = self.scheduler:After(self.period, function()
        if not self.alive then return end
        self.handle = nil
        local ok = pcall(self.driver.Tick, self.driver)
        if not ok or self.driver.alive == false then
            self:Close(); return
        end
        self:Schedule()
    end)
    if handle == nil then error("Timer did not schedule") end
    self.handle = handle
end

function Methods:Start()
    if self.alive then return false end
    self.alive = true
    local ok = pcall(self.Schedule, self)
    if not ok then self:Close(); return false end
    return true
end

function Methods:Close()
    if not self.alive then return false end
    self.alive = false
    if self.handle ~= nil then
        pcall(self.scheduler.Cancel, self.scheduler, self.handle)
        self.handle = nil
    end
    self.driver:Close()
    return true
end

return RuntimeLoop
