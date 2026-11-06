-- Decompiled with Potassium's decompiler.

local ServerClock = require(game:GetService("ReplicatedStorage"):WaitForChild("MW"):WaitForChild("ServerClock"));
local u1 = {};
local u2 = nil;
local u3 = nil;
local u4 = {};

local function identity(p5) -- Line: 7
    return p5.districtId .. ":" .. p5.userId .. ":" .. p5.memberIndex .. ":" .. tostring(p5.deploymentId or p5.at);
end;

local u6 = 0;
local u7 = {};

local function changed(p8) -- Line: 10
    -- upvalues: u7 (copy), u3 (ref)
    for _, v in ipairs(u7) do
        local success, result = pcall(v, u3, p8);

        if not success then
            warn("[MW] Recall display: " .. tostring(result));
        end;
    end;
end;

function u1.onChanged(p9) -- Line: 16
    -- upvalues: u7 (copy)
    table.insert(u7, p9);
end;

function u1.busy() -- Line: 17
    -- upvalues: u3 (ref)
    return u3 ~= nil;
end;

function u1.isPending(p10, p11, p12) -- Line: 18
    -- upvalues: u3 (ref)
    for _, v in ipairs(u3 and u3.targets or {}) do
        if v.userId == p11 and (v.memberIndex == p12 and (not p10 or v.districtId == p10)) then
            return true;
        end;
    end;

    return false;
end;

function u1.targets(p13, p14) -- Line: 24
    -- upvalues: u2 (ref), u4 (copy)
    local v15 = {};
    local v16 = u2 and u2.State.data;

    for i, v in ipairs(v16 and v16.crew or {}) do
        if not (i <= 1 or not (v.duty and (not p13 or v.duty == p13)) or p14 and i ~= p14) then
            local v17 = {
                districtId = v.duty,
                userId = u2.player.UserId,
                memberIndex = i,
                deploymentId = v.dutyToken,
                at = v.dutyAt,
                memberName = v.name,
                rarity = v.rarity
            };

            if u4[i] ~= v17.districtId .. ":" .. v17.userId .. ":" .. v17.memberIndex .. ":" .. tostring(v17.deploymentId or v17.at) then
                table.insert(v15, v17);
            end;
        end;
    end;

    return v15;
end;

local function finish(p18, p19) -- Line: 36
    -- upvalues: u3 (ref), u2 (ref), u4 (copy), changed (copy)
    if u3 ~= p18 or (type(p19) ~= "table" or p19.pending) then
        return;
    end;

    u3 = nil;

    for _, v in ipairs(p19.settled or {}) do
        if v.userId == u2.player.UserId then
            u4[v.memberIndex] = v.districtId .. ":" .. v.userId .. ":" .. v.memberIndex .. ":" .. tostring(v.deploymentId or v.at);
        end;
    end;

    changed(p19);
    u2.toast(p19.ok and "family" or "error", p19.msg or "Recall could not be confirmed. Refresh your crew.");
    local l_print = print;
    local string_format = string.format;
    local id = p18.id;
    local v20 = os.clock() - p18.startedAt;
    local v21 = os.clock() - p18.startedAt >= 8;
    l_print(string_format("[MW] Recall client request=%.0f total=%.3fs late=%s", id, v20, (tostring(v21))));
end;

function u1.start(p22) -- Line: 46
    -- upvalues: u3 (ref), u6 (ref), ServerClock (copy), changed (copy), finish (copy), u2 (ref)
    if u3 or #p22 == 0 then
        return;
    end;

    local v23 = ServerClock.now() * 1000;
    local math_floor_ret = math.floor(v23);
    u6 = math.max(u6 + 1, math_floor_ret);
    local u24 = {
        nextSubmit = 0,
        id = u6,
        targets = p22,
        startedAt = os.clock()
    };
    u3 = u24;
    changed();
    local u25 = {};

    local function call(u26, u27, u28, u29) -- Line: 52
        -- upvalues: u25 (copy), u3 (ref), u24 (copy), finish (ref)
        if u25[u27] then
            return;
        end;

        u25[u27] = true;
        task.spawn(function() -- Line: 55
            -- upvalues: u26 (copy), u27 (copy), u28 (copy), u29 (copy), u25 (ref), u3 (ref), u24 (ref), finish (ref)
            local success, result = pcall(function() -- Line: 56
                -- upvalues: u26 (ref), u27 (ref), u28 (ref), u29 (ref)
                return u26:InvokeServer(u27, u28, u29);
            end);
            u25[u27] = nil;

            if u3 ~= u24 then
                return;
            end;

            if success and type(result) == "table" then
                if result.code == "unknown_request" then
                    u24.nextSubmit = 0;

                    return;
                end;

                if result.code ~= "rate_limited" then
                    finish(u24, result);
                end;
            end;
        end);
    end;

    task.spawn(function() -- Line: 65
        -- upvalues: u3 (ref), u24 (copy), u2 (ref), u25 (copy), finish (ref)
        while u3 == u24 do
            local os_clock_ret = os.clock();

            if u24.nextSubmit <= os_clock_ret then
                u24.nextSubmit = os_clock_ret + 15;
                local TerritoryAction = u2.Remotes.TerritoryAction;
                local id = u24.id;
                local targets = u24.targets;

                if not u25.recallcrew then
                    u25.recallcrew = true;
                    local u30 = "recallcrew";
                    task.spawn(function() -- Line: 55
                        -- upvalues: TerritoryAction (copy), u30 (copy), id (copy), targets (copy), u25 (ref), u3 (ref), u24 (ref), finish (ref)
                        local success, result = pcall(function() -- Line: 56
                            -- upvalues: TerritoryAction (ref), u30 (ref), id (ref), targets (ref)
                            return TerritoryAction:InvokeServer(u30, id, targets);
                        end);
                        u25[u30] = nil;

                        if u3 ~= u24 then
                            return;
                        end;

                        if success and type(result) == "table" then
                            if result.code == "unknown_request" then
                                u24.nextSubmit = 0;

                                return;
                            end;

                            if result.code ~= "rate_limited" then
                                finish(u24, result);
                            end;
                        end;
                    end);
                end;
            end;

            if os_clock_ret - u24.startedAt >= 8 and not u24.warned then
                u24.warned = true;
                u2.toast("info", "Recall is still processing. You can keep browsing; it will update when confirmed.");
            end;

            local TerritoryStatus = u2.Remotes.TerritoryStatus;
            local id = u24.id;

            if not u25.recallstatus then
                u25.recallstatus = true;
                local u31 = "recallstatus";
                local u32 = nil;
                task.spawn(function() -- Line: 55
                    -- upvalues: TerritoryStatus (copy), u31 (copy), id (copy), u32 (copy), u25 (ref), u3 (ref), u24 (ref), finish (ref)
                    local success, result = pcall(function() -- Line: 56
                        -- upvalues: TerritoryStatus (ref), u31 (ref), id (ref), u32 (ref)
                        return TerritoryStatus:InvokeServer(u31, id, u32);
                    end);
                    u25[u31] = nil;

                    if u3 ~= u24 then
                        return;
                    end;

                    if success and type(result) == "table" then
                        if result.code == "unknown_request" then
                            u24.nextSubmit = 0;

                            return;
                        end;

                        if result.code ~= "rate_limited" then
                            finish(u24, result);
                        end;
                    end;
                end);
            end;

            task.wait(3);
        end;
    end);
end;

function u1.confirm(u33, p34) -- Line: 82
    -- upvalues: u3 (ref), u2 (ref), u1 (copy)
    if u3 or #u33 == 0 then
        return;
    end;

    u2.confirmDialog(p34 or "RECALL ALL HENCHMEN", "Withdraw " .. #u33 .. " of your henchmen from district defense? Worn henchmen need 10 minutes to regroup. Full-strength henchmen return without a cooldown.", "RECALL " .. #u33, function() -- Line: 86
        -- upvalues: u1 (ref), u33 (copy)
        u1.start(u33);
    end);
end;

function u1.init(p35) -- Line: 88
    -- upvalues: u2 (ref), u3 (ref), finish (copy)
    if u2 then
        return;
    end;

    u2 = p35;
    task.spawn(function() -- Line: 95
        -- upvalues: u2 (ref), u3 (ref), finish (ref)
        local TerritoryUpdate = u2.Remotes:WaitForChild("TerritoryUpdate");
        (typeof(TerritoryUpdate) == "Instance" and TerritoryUpdate and TerritoryUpdate or TerritoryUpdate.Instance).OnClientEvent:Connect(function(p36) -- Line: 98
            -- upvalues: u3 (ref), finish (ref)
            if type(p36) == "table" and (p36.kind == "recall" and (u3 and p36.requestId == u3.id)) then
                finish(u3, p36.result);
            end;
        end);
    end);
end;

return u1;