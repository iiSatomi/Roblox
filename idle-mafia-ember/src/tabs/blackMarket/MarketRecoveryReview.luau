-- Paused local cleanup only. Never invokes, retries, answers a check or resets a run.
local Review = {}
local function equal(a,b)
    if type(a)~=type(b) then return false end
    if type(a)~="table" then return a==b end
    for k,v in pairs(a) do if not equal(v,b[k]) then return false end end
    for k in pairs(b) do if a[k]==nil then return false end end
    return true
end
function Review.new(deps)
    local owner, env = deps.owner, deps.environment
    local feature=deps.feature or "marketSell"
    local closed, busy, staged = false, false, nil
    local function paused()
        local state=env.session:Status()
        return not closed and state.state=="paused" and state.active==nil and env.requested()==false
            and not state.storageFault and not env.checkpoint.fault
    end
    local function guard()
        if busy or env.busy() or not paused() then return nil,"Pause and finish active work before listing recovery" end
        local raw=env.currentSnapshot()
        local timed,now=pcall(env.clock.Now,env.clock)
        if type(raw)~="table" or type(raw.native)~="table" or raw.native.fullSync~=true
            or not timed or type(now)~="number" or now~=now or now<0 or now==math.huge
            or type(raw.capturedAt)~="number" or raw.capturedAt~=raw.capturedAt or raw.capturedAt<0
            or raw.capturedAt>now or now-raw.capturedAt>2 then return nil,"Current full account information required" end
        for _,field in ipairs({"session","account","place","release"}) do
            if raw[field]~=env.identity[field] then return nil,"Listing recovery account changed" end
        end
        local active=owner:Active()
        local buy=active and active.kind=="buy"
        local withdrawal=active and active.kind=="withdraw"
        local base=(buy or withdrawal) and active.baseline or active
        local attempts=buy and owner:BuyUsage().attempted or withdrawal and owner:WithdrawAttempts() or owner:ListingAttempts(feature)
        if not active or (active.kind~="list" and active.kind~="withdraw" and active.kind~="buy") or active.sourceKey~=deps.fingerprint
            or type(active.actionKey)~="string" or attempts==nil then return nil,"No reviewable runtime listing" end
        local known=owner:RuntimeUnsentReview()
        local kind, proof, description
        if known then kind,proof,description="unsent",known,"Release the proven unsent listing; refund only its own charged attempt."
        elseif active.stage=="prepared" then kind,proof,description="prepared",owner:PreparedReview(),"Discard this unsent preparation. No item is listed."
        elseif (buy or withdrawal) and active.stage=="observed" then
            proof=owner:ObservedIntermediateReview(raw,now)
            if proof then kind,description="observed","Stop this completed acquisition continuation and release its local hold. Items stay in inventory; attempts and Gold exposure stay charged." end
        elseif active.stage=="sent" then
            proof=owner:RejectedRuntimeReview(raw)
            if proof then kind,description="rejected","Release exactly rejected listing custody. Its attempt stays charged." end
        end
        if not proof then return nil,"Sent listing outcome remains held; no discard or replay is authorized" end
        local checkpointed=false
        for _,record in ipairs(env.checkpoint:Records()) do
            if kind=="observed" and (record.feature=="marketSell" or record.feature=="marketFlip") then
                return nil,"Finish pending trade recovery before releasing acquired items"
            end
            if record.feature==feature then
                if kind=="observed" then return nil,"Finish pending listing recovery before releasing withdrawn items" end
                if checkpointed or record.actionKey~=active.actionKey then return nil,"Other listing uncertainty needs review" end
                local data=env.checkpoint:Recovery(record.actionKey)
                local p=data and data.proposal
                local i=p and p.intent
                if not i or i.ownerGeneration~=active.preparedGeneration or i.sourceKey~=active.sourceKey
                    or i.itemId~=base.itemId or (not buy and i.quantity~=base.quantity)
                    or (buy and (i.kind~="marketBuy" or i.quantity~=1 or i.listingId~=base.listingId or i.quotedPrice~=base.price))
                    or (not buy and not withdrawal and i.ask~=active.ask)
                    or (withdrawal and (i.kind~="marketCollectionWithdraw" or i.checkpointFloor~=base.floor)) then
                    return nil,"Listing checkpoint identity changed"
                end
                local selected=buy and deps.buyEvidence or withdrawal and deps.withdrawEvidence or deps.evidence
                local input=p
                if buy or withdrawal or feature=="marketFlip" then input={} for k,v in pairs(p) do input[k]=v end input.preflightOnly=true end
                local baseline=selected and selected.capture(input,data.before)
                if not baseline or not equal(baseline,data.baseline) then return nil,"Listing checkpoint baseline changed" end
                for field,value in pairs(baseline) do
                    if not equal(base[field],value) then return nil,"Listing store baseline changed" end
                end
                if kind~="rejected" and data.reply~=nil then return nil,"Listing has a returned result" end
                if kind=="rejected" then
                    for _,field in ipairs({"ok","pending","code","moved"}) do
                        if not data.reply or data.reply[field]~=active.reply[field] then return nil,"Listing reply changed" end
                    end
                end
                checkpointed=true
            end
        end
        if not paused() then return nil,"Pause changed during listing review" end
        local latest=env.currentSnapshot()
        for _,field in ipairs({"session","account","place","release","revision","capturedAt"}) do
            if type(latest)~="table" or latest[field]~=raw[field] then return nil,"Listing snapshot changed during review" end
        end
        local sampled,latestNow=pcall(env.clock.Now,env.clock)
        if not sampled or type(latestNow)~="number" or latestNow~=latestNow
            or latestNow<now or latestNow-raw.capturedAt>2 then return nil,"Listing snapshot expired during review" end
        now=latestNow
        return {kind=kind,proof=proof,raw=raw,at=now,generation=owner.generation,attempted=attempts,
            actionKey=active.actionKey,preparedGeneration=active.preparedGeneration,
            checkpointed=checkpointed,description=description,itemId=base.itemId},nil
    end
    local result={}
    function result:Preview()
        staged=nil
        local view,reason=guard()
        if not view then return nil,reason end
        local ticket={}
        staged={view=view,ticket=ticket,at=view.at}
        return {kind=view.kind,itemId=view.itemId,attempted=view.attempted,
            description=view.description,ticket=ticket},nil
    end
    function result:Confirm(ticket)
        local previous=staged;staged=nil
        if not previous or previous.ticket~=ticket then return false,"Review this listing before confirming" end
        local view,reason=guard()
        if not view then return false,reason end
        if view.at<previous.at or view.at-previous.at>30 then return false,"Listing recovery review expired" end
        for _,field in ipairs({"kind","generation","actionKey","preparedGeneration","attempted","checkpointed"}) do
            if view[field]~=previous.view[field] then return false,"Listing record changed; review again" end
        end
        busy=true
        local ok,saved,why=pcall(function()
            if not paused() then return false,"Pause before confirming listing cleanup" end
            local accepted,failure
            if view.kind=="prepared" then
                accepted,failure=owner:RecordRuntimeUnsent(view.actionKey,view.preparedGeneration)
                if not accepted then return false,failure end
                local proof=owner:RuntimeUnsentReview()
                if not proof then return false,"Unsent proof unavailable" end
                accepted,failure=owner:ReleaseRuntimeUnsent(proof)
            elseif view.kind=="observed" then accepted,failure=owner:ReleaseObservedIntermediate(view.proof,view.raw,view.at)
            elseif view.kind=="unsent" then accepted,failure=owner:ReleaseRuntimeUnsent(view.proof)
            else accepted,failure=owner:ReleaseRejectedRuntimeList(view.proof,view.raw) end
            if not accepted then return false,failure end
            if not paused() then return false,"Local recovery saved; checkpoint cleanup waits for pause" end
            if view.checkpointed then return env.checkpoint:Resolve(view.actionKey,view.kind=="rejected" and "rejected" or "schedule_failed") end
            return true
        end)
        busy=false
        return ok and saved==true,ok and why or "Listing recovery save failed"
    end
    function result:Invalidate() staged=nil end
    function result:IsBusy() return busy end
    function result:Close() closed,staged=true,nil end
    return result
end
return Review
