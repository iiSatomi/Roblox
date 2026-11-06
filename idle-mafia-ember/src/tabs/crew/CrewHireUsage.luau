-- Independent empty-slot hire attempts/Cash exposure; only definitely-unsent refunds.
local Usage={}
local MAX=9007199254740991
local function int(v,lo,hi) return type(v)=="number" and v==v and v%1==0 and v>=lo and v<=hi end
function Usage.copy(raw)
    if raw==nil then return {version=1,attempted=0,spent=0} end
    if type(raw)~="table" or raw.version~=1 or not int(raw.attempted,0,1000) or not int(raw.spent,0,MAX)
        or raw.spent<raw.attempted or raw.attempted==0 and raw.spent~=0 then return nil end
    for k in pairs(raw) do if k~="version" and k~="attempted" and k~="spent" then return nil end end
    return {version=1,attempted=raw.attempted,spent=raw.spent}
end
function Usage.copyCharge(raw,feature,resources)
    if feature~="crewHire" or type(raw)~="table" or not int(raw.price,1,MAX)
        or not int(raw.attemptedBefore,0,999) or not int(raw.spentBefore,0,MAX-raw.price)
        or raw.spentBefore<raw.attemptedBefore or raw.attemptedBefore==0 and raw.spentBefore~=0
        or type(resources)~="table" or resources.cash~=raw.price then return nil end
    for k in pairs(resources) do if k~="cash" then return nil end end
    for k in pairs(raw) do if k~="price" and k~="attemptedBefore" and k~="spentBefore" then return nil end end
    return {price=raw.price,attemptedBefore=raw.attemptedBefore,spentBefore=raw.spentBefore}
end
function Usage.charge(raw,proposal)
    local u=Usage.copy(raw)
    local i=type(proposal)=="table" and proposal.intent
    if not u or type(i)~="table" or i.kind~="crewHire" or not int(i.maxAttempts,0,1000)
        or not int(i.maxSpend,0,MAX) then return nil,nil,"Hire allowance unavailable" end
    local c=Usage.copyCharge({price=i.cost,attemptedBefore=i.attemptedBefore,spentBefore=i.spentBefore},proposal.feature,proposal.resources)
    if not c or u.attempted~=c.attemptedBefore or u.spent~=c.spentBefore or u.attempted>=i.maxAttempts
        or u.spent+c.price>i.maxSpend then return nil,nil,"Hire allowance changed or exhausted" end
    return {version=1,attempted=u.attempted+1,spent=u.spent+c.price},c,nil
end
function Usage.holds(raw,c)
    local u=Usage.copy(raw)
    return u~=nil and u.attempted>=c.attemptedBefore+1 and u.spent>=c.spentBefore+c.price
end
function Usage.rollback(raw,c)
    local u=Usage.copy(raw)
    if not u or u.attempted~=c.attemptedBefore+1 or u.spent~=c.spentBefore+c.price then return nil end
    return {version=1,attempted=c.attemptedBefore,spent=c.spentBefore}
end
return Usage
