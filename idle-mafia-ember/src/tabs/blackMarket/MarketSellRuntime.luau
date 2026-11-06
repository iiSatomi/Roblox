-- One ordinary loose-item listing; native manual checks remain in their own UI.
local Runtime = {}
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not equal(value, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
function Runtime.new(deps, owner, research, feature)
    feature=feature or "marketSell"
    local flip=feature=="marketFlip"
    if type(owner) ~= "table" or type(research) ~= "table" or type(deps.clock) ~= "table" then return nil end
    local closed, evidence = false, deps.MarketListEvidence
    research:AttachSaleOwner(owner)
    local function matched(record, p)
        local i = type(p) == "table" and p.intent
        if type(record)~="table" or type(i)~="table" then return false end
        if record.kind=="buy" then
            return i.kind=="marketBuy" and record.actionKey==p.actionKey and record.sourceKey==i.sourceKey
                and record.preparedGeneration==i.ownerGeneration and record.baseline.itemId==i.itemId
                and record.baseline.listingId==i.listingId and record.baseline.price==i.quotedPrice
                and record.expectedAsk==i.expectedAsk
        end
        if record.kind=="withdraw" then
            return i.kind=="marketCollectionWithdraw" and record.actionKey==p.actionKey
                and record.preparedGeneration==i.ownerGeneration and record.sourceKey==i.sourceKey
                and record.baseline.itemId==i.itemId and record.baseline.quantity==i.quantity
                and record.plannedQuantity==i.plannedListingQuantity and record.expectedAsk==i.expectedAsk
        end
        return record.kind == "list" and record.actionKey == p.actionKey and record.preparedGeneration == i.ownerGeneration
            and record.sourceKey == i.sourceKey and record.itemId == i.itemId
            and record.quantity == i.quantity and record.ask == i.ask
    end
    local function gate()
        if closed or type(deps.marketPresence) ~= "table" or type(deps.marketPresence.check) ~= "function" then return false end
        local ok, allowed = pcall(deps.marketPresence.check)
        return ok and allowed == true
    end
    local function call(p)
        if p.intent.kind=="marketBuy" then return {remote="MarketAction",method="InvokeServer",arity=4,args={"buy",p.intent.listingId,1,p.intent.quotedPrice}} end
        if p.intent.kind=="marketCollectionWithdraw" then
            return {remote="CollectionAction",method="InvokeServer",arity=3,args={"withdraw",p.intent.itemId,p.intent.quantity}}
        end
        return {remote="MarketAction",method="InvokeServer",arity=4,
            args={"list",p.intent.itemId,p.intent.quantity,p.intent.ask}}
    end
    local result = {}
    result.read = function(raw,context)
        if flip then return research:FlipView(raw,context) end
        return research:SaleView(raw,context) end
    result.propose = function(view, settings)
        if closed then return nil, "Market listing owner closed" end
        local proposal, reason
        if flip then proposal,reason=research:PlanFlip(view,settings,owner) else proposal,reason=research:PlanSale(view, settings) end
        if proposal then return proposal, nil end
        return nil, "Market sale " .. tostring(view and view.itemId) .. ": " .. tostring(reason)
    end
    result.capture = function(p, raw)
        if flip then return research:CaptureFlip(p,raw,owner) end
        return research:CaptureSale(p, raw) end
    result.evaluate = function(p,before,after,reply,baseline)
        if p.intent.kind=="marketBuy" then return deps.MarketBuyEvidence.evaluate(p,before,after,reply,baseline) end
        if p.intent.kind=="marketCollectionWithdraw" then
            return deps.MarketCollectionWithdrawEvidence.evaluate(p,before,after,reply,baseline)
        end
        return evidence.evaluate(p,before,after,reply,baseline)
    end
    result.canDispatch = gate
    result.lifecycle = {
        prepare = function(p, before)
            if closed or p.intent.sourceKey ~= deps.fingerprint
                or owner.generation + 1 ~= p.intent.ownerGeneration
                then return false, "Listing owner changed" end
            if p.intent.kind=="marketBuy" then return owner:PrepareRuntimeBuy(p,before) end
            if p.intent.kind=="marketCollectionWithdraw" then
                if owner:WithdrawAttempts()~=p.intent.attemptedBefore then return false,"Withdrawal allowance changed" end
                return owner:PrepareRuntimeWithdraw(p,before,p.intent.maxAttempts)
            end
            if owner:ListingAttempts(feature)~=p.intent.attemptedBefore then return false,"Listing allowance changed" end
            local active=owner:Active()
            if active and (active.kind=="withdraw" or active.kind=="buy") and active.stage=="observed" then
                return owner:PrepareRuntimeFollowupList(p,before,deps.clock:Now(),p.intent.maxAttempts)
            end
            return owner:PrepareRuntimeOwnedList(p, before, p.intent.maxAttempts)
        end,
        authorize = function(p)
            if not gate() then return nil, "Native Market check required" end
            if p.intent.kind=="marketBuy" then
                local saved,reason=owner:AuthorizeRuntimeBuy(p)
                return saved and call(p) or nil,reason
            end
            local authorize=p.intent.kind=="marketCollectionWithdraw" and owner.AuthorizeRuntimeWithdraw or owner.AuthorizeRuntimeOwnedList
            local saved,reason=authorize(owner,p.actionKey,p.intent.ownerGeneration,p.intent.maxAttempts,p.intent.sourceKey)
            return saved and call(p) or nil, reason
        end,
        returned = function(p, reply)
            if closed then return false, "Listing owner closed" end
            local saved, reason = owner:RecordRuntimeReturn(p.actionKey, p.intent.ownerGeneration, reply)
            if saved and type(deps.marketPresence) == "table" and type(deps.marketPresence.handle) == "function" then
                pcall(deps.marketPresence.handle, reply)
            end
            return saved, reason
        end,
        resolve = function(p, outcome, after)
            if closed or not matched(owner:Active(), p) then return false, "Listing resolution owner changed" end
            if outcome == "confirmed" then
                local state = owner:Reconcile(after)
                if state ~= "observed" then return false, "Listing effect remains uncertain" end
                if owner:Active().kind=="buy" then research:AcquisitionConfirmed();return true end
                if owner:Active().kind=="withdraw" then return true end
                return owner:ClearObserved()
            elseif outcome == "rejected" then
                local review, reason = owner:RejectedRuntimeReview(after)
                if not review then return false, reason end
                return owner:ReleaseRejectedRuntimeList(review, after)
            end
            return false, "Listing result remains uncertain"
        end,
        unsent = function(p)
            if closed then return false, "Listing owner closed" end
            if owner:Active() == nil then return true end
            if not matched(owner:Active(), p) then return false, "Unsent listing owner changed" end
            local recorded, reason = owner:RecordRuntimeUnsent(p.actionKey, p.intent.ownerGeneration)
            if not recorded then return false, reason end
            local review
            review, reason = owner:RuntimeUnsentReview()
            if not review then return false, reason end
            return owner:ReleaseRuntimeUnsent(review)
        end,
        abandonedUnsent = function(p)
            return owner:RecordRuntimeUnsent(p.actionKey, p.intent.ownerGeneration)
        end,
    }
    function result.recoverSaved(data, after)
        if closed or type(data) ~= "table" or type(data.proposal) ~= "table" then return nil end
        local p, baseline = data.proposal, data.baseline
        if p.feature ~= feature or type(p.intent) ~= "table" or p.intent.sourceKey ~= deps.fingerprint
            or type(p.resources) ~= "table" then return nil end
        local buy=p.intent.kind=="marketBuy"
        local withdrawal=p.intent.kind=="marketCollectionWithdraw"
        if buy then
            if p.resources.gold_bar~=p.intent.quotedPrice then return nil end
        elseif withdrawal then
            if next(p.resources)~=nil then return nil end
        elseif p.intent.kind~="marketList" or p.resources[p.intent.itemId]~=p.intent.quantity then return nil end
        for id in pairs(p.resources) do if id ~= (buy and "gold_bar" or p.intent.itemId) then return nil end end
        local input=p
        if withdrawal or buy or flip then input={} for key,value in pairs(p) do input[key]=value end input.preflightOnly=true end
        local selected=buy and deps.MarketBuyEvidence or withdrawal and deps.MarketCollectionWithdrawEvidence or evidence
        local expected = selected.capture(input, data.before)
        if not expected or not equal(expected, baseline) then return nil end
        local active = owner:Active()
        if data.reply == nil then
            local receipt = owner:RuntimeUnsentReceipt(p.actionKey, p.intent.ownerGeneration)
            if receipt and matched(receipt.transaction, p) then return "known_unsent" end
        end
        if type(data.reply)=="table" and data.reply.ok==false then
            local receipt=owner:RuntimeRejectedReceipt(p.actionKey,p.intent.ownerGeneration)
            if receipt and matched(receipt.transaction,p) then
                local original=(buy or withdrawal) and receipt.transaction.baseline or receipt.transaction
                local outcome=selected.evaluateStored(original,after,data.reply)
                local sameReply=true
                for _,field in ipairs({"ok","pending","code","moved"}) do
                    if data.reply[field]~=receipt.transaction.reply[field] then sameReply=false end
                end
                if sameReply and outcome=="rejected" then return "rejected" end
            end
        end
        if active and not matched(active, p) then return nil end
        if active and data.reply == nil then
            local review = owner:RuntimeUnsentReview()
            if review and matched(review.transaction, p) then
                local released = owner:ReleaseRuntimeUnsent(review)
                return released and "known_unsent" or nil
            end
        end
        local outcome
        if buy then outcome=selected.recoverSaved(data,after)
        elseif withdrawal then
            if type(data.reply)~="table" then return nil end
            outcome=selected.evaluateStored(baseline,after,data.reply)
            if outcome~="confirmed" and outcome~="rejected" then return nil end
        else outcome=evidence.recoverSaved(data, after) end
        local attempts=buy and owner:BuyUsage().attempted or withdrawal and owner:WithdrawAttempts() or owner:ListingAttempts(feature)
        if not outcome or attempts ~= p.intent.attemptedBefore + 1 then return nil end
        if (buy or withdrawal) and not active then return nil end
        if active then
            local saved = result.lifecycle.resolve(p, outcome, after)
            return saved and outcome or nil
        end
        return outcome -- Store cleanup committed before the generic checkpoint cleanup.
    end
    result.lifecycle.recover = result.recoverSaved
    if type(deps.MarketRecoveryReview)=="table" then
        result.lifecycle.recoveryFactory=function(environment)
            return deps.MarketRecoveryReview.new({owner=owner,feature=feature,evidence=evidence,buyEvidence=deps.MarketBuyEvidence,withdrawEvidence=deps.MarketCollectionWithdrawEvidence,
                fingerprint=deps.fingerprint,environment=environment})
        end
    end
    function result:Close() closed = true end
    return result
end
return Runtime
