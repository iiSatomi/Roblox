-- Native act simulator: counter and pending state belong to the game boundary.
return function(f)
    local raw = f.remotes:Add(f.node("HeistAction", "RemoteFunction"))
    f.wrapped.HeistAction = {Name = "HeistAction", Instance = raw,
        InvokeServer = function() error("Controller must use native act, never raw mutation") end}
    local function init() end
    local function invokeMutation() end
    local function paint() end
    local function refresh() end
    local pendingCallback
    local a = {[2] = 7, [3] = false, [4] = paint, [5] = invokeMutation,
        [6] = f.ctx, [7] = refresh}
    local calls = {}
    local function act(action, arg1, callback)
        assert(a[1] == nil and a[3] == false)
        a[2] = a[2] + 1
        a[1] = {sequence = a[2], actionName = action, arg1 = arg1, startedAt = 0}
        a[3], pendingCallback = true, callback
        calls[#calls + 1] = {action = action, arg1 = arg1, sequence = a[2]}
    end
    local tab = f.root.Parent:Add(f.node("Heists", "Frame"))
    local actIndex = f.game.PlaceVersion == 654 and 37 or 38
    local first = {[1] = f.ctx, [2] = tab, [actIndex] = act}
    local invocation = {[2] = f.ctx}
    f.upvalues[init], f.upvalues[act], f.upvalues[invokeMutation] = first, a, invocation
    f.client:Add(f.node("HeistsTab", "ModuleScript")).Value = {init = init}
    f.heistInit, f.heistAct, f.heistInvocation, f.heistCalls = first, a, invocation, calls
    f.finishHeist = function(reply)
        local callback = pendingCallback
        a[1], a[3], pendingCallback = nil, false, nil
        if reply.ok and callback then callback(reply) end
    end
    return f
end
