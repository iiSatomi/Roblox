-- Local input heartbeat for Idle Mafia. Does not intercept native reconnects.
-- Inspect: getgenv().__IdleMafiaAntiIdle:Status()
-- Stop:    getgenv().__IdleMafiaAntiIdle:Stop()
local GAME_ID, PLACE_ID = 10643795368, 73897506680154
local INTERVAL, MIN_GAP, MAX_FAILURES = 60, 5, 3
local KEY = "__IdleMafiaAntiIdle"
local handle = {}
local running, attempts, successes, failures = false, 0, 0, 0
local lastError, stoppedReason, lastAt, lastCause
local timer, connection, inFlight

function handle:Status()
    return { version = "1.0.0", running = running, interval = INTERVAL,
        attempts = attempts, successes = successes, consecutiveFailures = failures,
        lastError = lastError, stoppedReason = stoppedReason,
        lastAt = lastAt, lastCause = lastCause }
end

function handle:Stop(reason)
    if not running then return false end
    running, stoppedReason = false, reason or "Stopped by user"
    if timer then pcall(task.cancel, timer); timer = nil end
    if connection then pcall(connection.Disconnect, connection); connection = nil end
    return true
end

local function inScope()
    return game.GameId == GAME_ID and game.PlaceId == PLACE_ID
end
local startupDeadline = os.clock() + 30
-- Autoexec can run before the experience IDs or LocalPlayer are available.
while not inScope() and (game.GameId == 0 or game.GameId == GAME_ID)
    and (game.PlaceId == 0 or game.PlaceId == PLACE_ID) and os.clock() < startupDeadline do
    task.wait(0.25)
end
if not inScope() then
    stoppedReason = "Outside Idle Mafia game/place"
    return handle
end

local environment = _G
if type(getgenv) == "function" then
    local ok, value = pcall(getgenv)
    if not ok or type(value) ~= "table" then
        lastError, stoppedReason = "Executor environment unavailable", "Startup failed"
        warn("[Idle Mafia anti-idle] " .. lastError)
        return handle
    end
    environment = value
end
local previous = environment[KEY]
if previous ~= nil then
    local ok = type(previous) == "table" and type(previous.Stop) == "function"
        and pcall(previous.Stop, previous, "Replaced by a newer anti-idle instance")
    if ok then
        local checked, status = false, nil
        if type(previous.Status) == "function" then checked, status = pcall(previous.Status, previous) end
        ok = checked and type(status) == "table" and status.running == false
    end
    if not ok then
        lastError, stoppedReason = "Previous anti-idle instance could not stop", "Startup failed"
        warn("[Idle Mafia anti-idle] " .. lastError)
        return handle
    end
end

local ok, player, virtualUser = pcall(function()
    local players = game:GetService("Players")
    local user = game:GetService("VirtualUser")
    while not players.LocalPlayer and inScope() and os.clock() < startupDeadline do
        task.wait(0.25)
    end
    assert(inScope(), "Game/place changed while waiting for LocalPlayer")
    assert(players.LocalPlayer, "Local player unavailable; rerun after joining")
    return players.LocalPlayer, user
end)
if not ok then
    lastError, stoppedReason = tostring(player), "Startup failed"
    warn("[Idle Mafia anti-idle] " .. lastError)
    return handle
end
environment[KEY], running = handle, true

local function pulse(cause)
    if not running or inFlight or environment[KEY] ~= handle then return end
    if not inScope() then handle:Stop("Game/place changed"); return end
    local now = os.clock()
    if lastAt and now - lastAt < MIN_GAP then return end
    inFlight, lastAt, lastCause, attempts = true, now, cause, attempts + 1
    local captured, reason = pcall(function()
        assert(workspace.CurrentCamera, "Current camera unavailable")
        virtualUser:CaptureController()
        if not running or environment[KEY] ~= handle then return end
        local camera = workspace.CurrentCamera
        assert(camera, "Current camera unavailable")
        virtualUser:ClickButton2(Vector2.new(0, 0), camera.CFrame)
    end)
    inFlight = false
    if not running or environment[KEY] ~= handle then return end
    if captured then
        successes, failures, lastError = successes + 1, 0, nil
    else
        failures, lastError = failures + 1, tostring(reason)
        warn("[Idle Mafia anti-idle] Input failed (" .. failures .. "/" .. MAX_FAILURES .. "): " .. lastError)
        if failures >= MAX_FAILURES then
            handle:Stop("Input failed three consecutive times; inspect Status and rerun")
        end
    end
end

local connected, result = pcall(function()
    return player.Idled:Connect(function() pulse("Idled") end)
end)
if not connected then
    lastError = tostring(result)
    warn("[Idle Mafia anti-idle] Idle event unavailable: " .. lastError)
    handle:Stop("Could not subscribe to Player.Idled")
    return handle
end
connection = result

local schedule
schedule = function()
    if not running or environment[KEY] ~= handle then return end
    local scheduled, result = pcall(task.delay, INTERVAL, function()
        timer = nil
        pulse("Periodic")
        schedule()
    end)
    if not scheduled then
        lastError = tostring(result)
        warn("[Idle Mafia anti-idle] Timer unavailable: " .. lastError)
        handle:Stop("Could not schedule input heartbeat")
        return
    end
    timer = result
end

pulse("Startup")
schedule()
if running then
    print("[Idle Mafia anti-idle] Started; local input every 60 seconds with Idled fallback. Inspect " .. KEY .. ":Status().")
end
return handle
