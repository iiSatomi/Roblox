-- An injected monotonic elapsed clock. Wall-clock/server time is separate.
local Clock = {}
local Methods = {}
Methods.__index = Methods

function Clock.new(nowFn)
    assert(type(nowFn) == "function", "Clock needs a time reader")
    return setmetatable({ read = nowFn, last = nil }, Methods)
end

function Methods:Now()
    local sample = self.read()
    assert(type(sample) == "number" and sample == sample
        and sample >= 0 and sample < math.huge, "Invalid clock sample")
    if self.last ~= nil and sample < self.last then return self.last end
    self.last = sample
    return sample
end

return Clock
