-- Source-defined Market calls; runtime owners separately guard listing/rental emission.
local MarketCallPlan = {}

local function integer(value, minimum)
    return type(value) == "number" and value == value
        and value % 1 == 0 and value >= minimum
        and value < math.huge
end

function MarketCallPlan.describe(proposal)
    local intent = type(proposal) == "table" and proposal.intent
    if type(proposal)=="table" and proposal.feature=="marketSell" and type(intent)=="table"
        and intent.kind=="marketCollectionWithdraw" and type(intent.itemId)=="string"
        and #intent.itemId>0 and #intent.itemId<=120 and intent.itemId:match("^[%w_%-]+$")
        and integer(intent.quantity,1) and intent.quantity<=999
        and type(intent.sourceKey)=="string" and #intent.sourceKey==64 and intent.sourceKey:match("^[%x]+$")
        and integer(intent.ownerGeneration,1) and integer(intent.attemptedBefore,0)
        and integer(intent.maxAttempts,1) and intent.maxAttempts<=20 and intent.attemptedBefore<intent.maxAttempts
        and proposal.actionKey=="market-withdraw:"..intent.sourceKey..":"..tostring(intent.ownerGeneration)..":"..intent.itemId
        and type(proposal.resources)=="table" and next(proposal.resources)==nil then
        return {remote="CollectionAction",method="InvokeServer",arity=3,args={"withdraw",intent.itemId,intent.quantity}},nil
    end
    if type(proposal)=="table" and proposal.feature=="marketFlip" and type(intent)=="table" and intent.kind=="marketBuy"
        and (type(intent.listingId)=="string" and #intent.listingId>0 and #intent.listingId<=160 or integer(intent.listingId,1))
        and type(intent.itemId)=="string" and #intent.itemId>0 and #intent.itemId<=120
        and intent.quantity==1 and integer(intent.quotedPrice,1) and intent.quotedPrice<=9999999
        and type(intent.sourceKey)=="string" and #intent.sourceKey==64 and intent.sourceKey:match("^[%x]+$")
        and integer(intent.ownerGeneration,1) and integer(intent.maxAttempts,1) and intent.maxAttempts<=20
        and integer(intent.attemptedBefore,0) and intent.attemptedBefore<intent.maxAttempts
        and integer(intent.spentBefore,0) and integer(intent.sessionBudget,1)
        and intent.spentBefore+intent.quotedPrice<=intent.sessionBudget
        and proposal.actionKey=="market-buy:"..intent.sourceKey..":"..tostring(intent.ownerGeneration)..":"..tostring(intent.listingId)
        and type(proposal.resources)=="table" and proposal.resources.gold_bar==intent.quotedPrice then
        for resource in pairs(proposal.resources) do if resource~="gold_bar" then return nil,"Unexpected buy exposure" end end
        return {remote="MarketAction",method="InvokeServer",arity=4,args={"buy",intent.listingId,1,intent.quotedPrice}},nil
    end
    if type(proposal) == "table" and (proposal.feature == "marketSell" or proposal.feature=="marketFlip") and type(intent) == "table"
        and intent.kind == "marketList" and type(intent.itemId) == "string"
        and #intent.itemId > 0 and #intent.itemId <= 120 and intent.itemId:match("^[%w_%-]+$")
        and integer(intent.quantity, 1) and intent.quantity <= 999
        and integer(intent.ask, 2) and intent.ask <= 9999999
        and type(intent.sourceKey) == "string" and #intent.sourceKey == 64 and intent.sourceKey:match("^[%x]+$")
        and integer(intent.ownerGeneration, 1) and intent.ownerGeneration <= 9007199254740991
        and integer(intent.attemptedBefore,0)
        and integer(intent.maxAttempts,1) and intent.maxAttempts<=20
        and (proposal.feature=="marketFlip" and intent.attemptedBefore<400 and integer(intent.copyAttemptsBefore,0)
            and intent.copyAttemptsBefore<intent.maxAttempts
            or proposal.feature=="marketSell" and intent.attemptedBefore<intent.maxAttempts)
        and proposal.actionKey == (proposal.feature=="marketFlip" and "market-flip-list:" or "market-list:") .. intent.sourceKey .. ":" .. tostring(intent.ownerGeneration) .. ":" .. intent.itemId
        and type(proposal.resources) == "table" and proposal.resources[intent.itemId] == intent.quantity then
        for id in pairs(proposal.resources) do if id ~= intent.itemId then return nil, "Unexpected listing resource" end end
        return {remote="MarketAction",method="InvokeServer",arity=4,args={"list",intent.itemId,intent.quantity,intent.ask}}, nil
    end
    if type(proposal) == "table" and proposal.feature == "marketRent" and type(intent) == "table"
        and intent.kind == "marketRent" and intent.periods == 1 and integer(intent.cost, 1) and intent.cost <= 1000
        and integer(intent.durationSeconds, 3600) and intent.durationSeconds <= 2592000
        and type(intent.sourceKey) == "string" and #intent.sourceKey == 64 and intent.sourceKey:match("^[%x]+$")
        and integer(intent.attemptedBefore, 0) and integer(intent.spentBefore, 0)
        and integer(intent.maxAttempts, 1) and intent.maxAttempts <= 20 and intent.attemptedBefore < intent.maxAttempts
        and integer(intent.maxGoldSpend, 1) and intent.maxGoldSpend <= 1000
        and intent.spentBefore + intent.cost <= intent.maxGoldSpend
        and type(proposal.resources) == "table" and proposal.resources.gold_bar == intent.cost then
        for resource in pairs(proposal.resources) do if resource ~= "gold_bar" then return nil, "Unexpected rental resource" end end
        return {remote = "MarketAction", method = "InvokeServer", arity = 4, args = {"rent", 1},
            source = "saved MarketTab one-period Gold rental"}, nil
    end
    if type(proposal) == "table"
        and proposal.feature == "marketManage"
        and type(intent) == "table"
        and intent.kind == "marketCollectEarnings"
        and integer(intent.earningsBefore, 1)
        and integer(intent.goldBefore, 0) then
        return { remote = "MarketAction", method = "InvokeServer",
            arity = 4, args = { "collect" },
            source = "saved MarketTab sold-earnings claim" }, nil
    end
    return nil, "Unverified Market transaction call"
end

return MarketCallPlan
