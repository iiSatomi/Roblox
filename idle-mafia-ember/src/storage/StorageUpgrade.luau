-- Explicit reviewed code authorization. Data/evidence retain their original release.
local StorageUpgrade = {}
local Methods = {}
Methods.__index = Methods
local MAX = 9007199254740991
local writers = {}
local dataFamilies = {checkpoint=true,["market-rent"]=true,payouts=true,["player-fights"]=true,["territory-recall"]=true}
local DEFAULT_CARRY_DIRECTORY = "IdleMafiaEmberCompletion655/checkpoints"
local checkpointFields = {version=true, records=true, requestHighwater=true, favorUsage=true,
    sabotageUsage=true, bossUsage=true, globalClaimUsage=true, globalAttackUsage=true,
    familyClaimUsage=true, familyAttackUsage=true, bossShopUsage=true, familyContributionUsage=true,
    eventShopUsage=true, marketRentUsage=true, crewHireUsage=true, playerFightUsage=true,
    chestUsage=true, chestUsageInitialized=true, shopUsage=true, shopUsageInitialized=true,
    stationAttempts=true, prestigeAttempts=true, residencyAttempts=true}
local function text(value, maximum)
    return type(value)=="string" and #value>0 and #value<=maximum and not value:find("[%c]")
end
local function integer(value, low)
    return type(value)=="number" and value==value and value>=low and value<=MAX and value%1==0
end
local function sha(value) return type(value)=="string" and #value==64 and value:match("^[a-f0-9]+$")~=nil end
local function safeDirectory(value)
    if not text(value,200) or value:sub(1,1)=="/" or value:find("\\",1,true) or value:find("//",1,true) then return false end
    for part in value:gmatch("[^/]+") do
        if part=="." or part==".." or not part:match("^[%w_.%-]+$") then return false end
    end
    return true
end
local function same(a,b)
    if type(a)~=type(b) then return false end
    if type(a)~="table" then return a==b end
    for k,v in pairs(a) do if not same(v,b[k]) then return false end end
    for k in pairs(b) do if a[k]==nil then return false end end
    return true
end
local function tag(scope)
    return #scope.account..":"..scope.account..#scope.place..":"..scope.place
end
local function checkpointKey(scope, release)
    return "idle-mafia-ember:checkpoint:v1:"..tag(scope)..#release..":"..release
end
local function take(body)
    local n,rest=string.match(body,"^(%d+):(.*)$");n=tonumber(n)
    if not n or n<1 or n>160 or type(rest)~="string" or string.len(rest)<n then return nil end
    return rest:sub(1,n),rest:sub(n+1)
end
local function keyScope(key)
    local family,body=key:match("^idle%-mafia%-ember:([%w%-]+):v1:(.*)$")
    if not body then return nil end
    local account,rest=take(body);if not account then return nil end
    local place,tail=take(rest);if not place then return nil end
    local release,suffix=take(tail)
    return {account=account,place=place,release=release,suffix=suffix,family=family}
end
function StorageUpgrade.new(deps)
    local i=type(deps)=="table" and deps.identity
    if type(i)~="table" or not text(i.account,160) or not text(i.place,160) or not text(i.release,160)
        or type(deps.store)~="table" or deps.store.strictRecovery~=true
        or type(deps.store.Read)~="function" or type(deps.store.Write)~="function"
        or type(deps.store.Current)~="function" or type(deps.store.ListKeys)~="function"
        or type(deps.files)~="table" or type(deps.files.ReadFile)~="function" or type(deps.files.IsDirectory)~="function"
        or not safeDirectory(deps.directory)
        or type(deps.codec)~="table" or type(deps.codec.Encode)~="function" or type(deps.codec.Decode)~="function"
        or type(deps.sha256)~="function" or type(deps.modules)~="table"
        or type(deps.modules.Checkpoint)~="table" or type(deps.modules.Checkpoint.new)~="function"
        or type(deps.modules.PendingAction)~="table" or type(deps.modules.ResourceReservations)~="table"
        or deps.current~=nil and type(deps.current)~="function" then return nil,"Storage upgrade dependencies unavailable" end
    local identity={account=i.account,place=i.place,release=i.release,session=i.session}
    local self=setmetatable({deps=deps,identity=identity,store=deps.store},Methods)
    self.ownerKey="idle-mafia-ember:release-owner:v1:"..tag(identity)
    self.receiptPrefix="idle-mafia-ember:storage-upgrade:v1:"..tag(identity)
    self.archivePrefix="idle-mafia-ember:storage-upgrade-source:v1:"..tag(identity)
    self.receiptKey=self.receiptPrefix..#identity.release..":"..identity.release
    return self,nil
end
function Methods:Alive()
    if self.deps.current==nil then return true end
    local ok,current=pcall(self.deps.current);return ok and current==true
end
function Methods:Hash(bytes)
    local ok,value=pcall(self.deps.sha256,bytes)
    if not ok or not sha(value) then error("Storage upgrade hash unavailable",0) end
    return value
end
function Methods:ArchiveKey(value)
    local parts={value.codeRelease,value.kind,value.sourceDirectory,value.key,tostring(value.generation),self:Hash(value.payload)}
    local encoded={}
    for index,part in ipairs(parts) do encoded[index]=#part..":"..part end
    return self.archivePrefix..self:Hash(table.concat(encoded))
end
function Methods:ReadArchive(key)
    local slot=self.store:Current(key)
    local value=slot and slot.value
    if type(value)~="table" or value.version~=1 or value.account~=self.identity.account or value.place~=self.identity.place
        or not text(value.codeRelease,160) or (value.kind~="canonical" and value.kind~="carry")
        or not safeDirectory(value.sourceDirectory) or not text(value.key,512) or not integer(value.generation,1)
        or type(value.payload)~="string" or #value.payload>1048576 or self:ArchiveKey(value)~=key then
        error("Invalid original-source archive",0)
    end
    return slot,value
end
function Methods:Archive(row,kind,directory)
    if type(row)~="table" or not text(row.key,512) or not integer(row.generation,1)
        or type(row.payload)~="string" or #row.payload>1048576 then error("Invalid source archive input",0) end
    local value={version=1,account=self.identity.account,place=self.identity.place,codeRelease=self.identity.release,
        kind=kind,sourceDirectory=directory,key=row.key,generation=row.generation,payload=row.payload}
    local key=self:ArchiveKey(value)
    local existing=self.store:Current(key)
    if not existing then
        if self.store:Write(key,value)~=true then error("Original-source archive write unconfirmed",0) end
    end
    local slot,observed=self:ReadArchive(key)
    if not same(value,observed) then error("Original-source archive changed",0) end
    return {key=key,generation=slot.generation,sha256=self:Hash(slot.payload)}
end
function Methods:ResolveArchives(references,kind,codeRelease,directory,chain)
    if type(references)~="table" or #references>256 then error("Source archive reference limit",0) end
    local sources={}
    for index,reference in ipairs(references) do
        if type(reference)~="table" or not text(reference.key,512) or not integer(reference.generation,1)
            or not sha(reference.sha256) then error("Invalid source archive reference",0) end
        local slot,value=self:ReadArchive(reference.key)
        if slot.generation~=reference.generation or self:Hash(slot.payload)~=reference.sha256
            or value.kind~=kind or value.codeRelease~=codeRelease or value.sourceDirectory~=directory then
            error("Original-source archive reference changed",0)
        end
        chain[reference.key]=true
        sources[index]={key=value.key,generation=value.generation,payload=value.payload}
    end
    for key in pairs(references) do if not integer(key,1) or key>#sources then error("Sparse archive references",0) end end
    return sources
end
function Methods:Checkpoint(value,release)
    if type(value)~="table" or value.version~=1 then error("Unsupported checkpoint version",0) end
    for field in pairs(value) do if not checkpointFields[field] then error("Unsupported checkpoint field",0) end end
    local m=self.deps.modules
    local reader={strictRecovery=true,Read=function()return value end,Write=function()error("Validation is read-only")end}
    local cp=m.Checkpoint.new(reader,m.FamilyContributionUsage,m.ResourceReservations,m.PendingAction,
        m.EventShopUsage,m.MarketRentUsage,m.CrewHireUsage,m.PlayerFightUsage,m.Chests,m.ShopBuy)
    local records,why=cp:Load(self.identity.account,self.identity.place,release)
    if not records then error(why or "Checkpoint validation failed",0) end
    return cp
end
function Methods:Legacy()
    local root="IdleMafiaFluent/"..self.identity.place.."/"..self.identity.account.."/"
    local paths={}
    for _,name in ipairs({"settings","configs","action-journal","market-flip","market-sell","market-memory",
        "property-review","gear-plan","high-value-targets","combat-evidence"}) do paths[#paths+1]=root..name..".json" end
    paths[#paths+1]=root.."configs.json.bak"
    paths[#paths+1]="IdleMafiaMugTracker/"..self.identity.account.."/mugs.json"
    local result,total={},0
    for _,path in ipairs(paths) do
        local bytes=self.deps.files:ReadFile(path)
        if bytes~=nil then
            if type(bytes)~="string" or #bytes>2097152 then error("Legacy review exceeds limits",0) end
            total=total+#bytes;if total>16777216 then error("Legacy review exceeds limits",0) end
            result[path]=self:Hash(bytes)
        end
    end
    return result
end
function Methods:Carry(review,storageRelease)
    local module=self.deps.modules.StorageUsageCarry
    local known=type(module)=="table" and module.DefaultSourceDirectory or DEFAULT_CARRY_DIRECTORY
    local checked,exists=pcall(self.deps.files.IsDirectory,self.deps.files,known)
    if not checked or type(exists)~="boolean" then error("External storage discovery unavailable",0) end
    local provided=self.deps.usageCarry
    if provided~=nil then return provided end
    if review==nil and not exists then return nil end
    if type(module)~="table" or type(module.new)~="function" then error("Typed external usage carry required",0) end
    local directory=review and review.sourceDirectory or known
    if not safeDirectory(directory) or directory==self.deps.directory.."/checkpoints"
        or exists and directory~=known then error("Known external storage source omitted",0) end
    local redundant=self.deps.modules.RedundantStore
    if type(redundant)~="table" or type(redundant.new)~="function" then error("Strict carry source reader unavailable",0) end
    local files={ReadFile=function(_,path)return self.deps.files:ReadFile(path)end,
        ListFiles=function(_,path)return self.deps.files:ListFiles(path)end,
        WriteFile=function()error("External carry source is read-only",0)end}
    local source=redundant.new(files,self.deps.codec,self.deps.sha256,directory,{strictRecovery=true})
    local original=source:Read(self.ownerKey)
    local sourceRelease=review and review.sourceRelease or type(original)=="table" and original.release
    local result,why=module.new({sourceStore=source,sourceDirectory=directory,sourceRelease=sourceRelease,
        identity=self:Result(storageRelease).identity,modules=self.deps.modules,codec=self.deps.codec,sha256=self.deps.sha256})
    if not result then error(why or "Typed external source validation failed",0) end
    return result
end
function Methods:AdoptCarry(certificate,storageRelease,cp)
    local review=certificate.review.carryReview
    local carry=self:Carry(review,storageRelease)
    if not carry then return nil,0 end
    if type(review)~="table" or type(certificate.carrySources)~="table" or type(carry.Adopt)~="function" then
        error("Exact typed carry certificate required",0)
    end
    local guard,why=carry:Adopt(review,certificate.carrySources,cp)
    if type(guard)~="table" or type(guard.Check)~="function" or type(guard.BindCheckpoint)~="function"
        or not integer(review.requestHighwaterFloor,0) then error(why or "Usage carry adoption failed",0) end
    return guard,review.requestHighwaterFloor
end
function Methods:Result(storageRelease,guard,floor)
    return {identity={account=self.identity.account,place=self.identity.place,session=self.identity.session,
        release=storageRelease},sourceRelease=self.identity.release,usageCarryGuard=guard,requestHighwaterFloor=guard and floor or nil}
end
function Methods:Certificate(owner,chain,depth)
    chain,depth=chain or {},depth or 0
    if depth>=16 then error("Storage lineage review depth exceeded",0) end
    if type(owner)~="table" or owner.version~=2 or owner.account~=self.identity.account
        or owner.place~=self.identity.place or not text(owner.release,160) or not text(owner.storageRelease,160)
        or not text(owner.receiptKey,512) or owner.receiptKey~=self.receiptPrefix..#owner.release..":"..owner.release
        or not sha(owner.receiptHash) or not integer(owner.receiptGeneration,1) then error("Invalid storage lineage owner",0) end
    if chain[owner.receiptKey] then error("Storage lineage certificate cycle",0) end
    chain[owner.receiptKey]=true
    local receipt=self.store:Current(owner.receiptKey)
    if not receipt or receipt.generation~=owner.receiptGeneration or self:Hash(receipt.payload)~=owner.receiptHash then
        error("Storage lineage certificate changed",0)
    end
    local stored=receipt.value
    local cert={}
    if type(stored)=="table" then for key,value in pairs(stored) do cert[key]=value end end
    if type(cert)~="table" or cert.version~=1 or type(cert.review)~="table" or type(cert.sources)~="table"
        or cert.review.account~=owner.account or cert.review.place~=owner.place
        or cert.review.codeRelease~=owner.release or cert.review.storageRelease~=owner.storageRelease
        or type(cert.review.inventory)~="table" or #cert.review.inventory>256
        or #cert.sources~=#cert.review.inventory then error("Invalid storage lineage certificate",0) end
    cert.sources=self:ResolveArchives(cert.sources,"canonical",owner.release,self.deps.directory.."/checkpoints",chain)
    if cert.review.carryReview~=nil then
        cert.carrySources=self:ResolveArchives(cert.carrySources,"carry",owner.release,cert.review.carryReview.sourceDirectory,chain)
    elseif cert.carrySources~=nil then error("Unbound carry source archive",0) end
    for index,row in ipairs(cert.review.inventory) do
        local source=cert.sources[index]
        if type(row)~="table" or type(source)~="table" or source.key~=row.key
            or source.generation~=row.generation or type(source.payload)~="string"
            or #source.payload>1048576 or self:Hash(source.payload)~=row.sha256 then error("Archived source changed",0) end
        if row.key==self.ownerKey then
            local original=self.deps.codec:Decode(source.payload)
            if type(original)=="table" and original.version==2 then self:Certificate(original,chain,depth+1) end
        end
    end
    return cert,chain
end
function Methods:Snapshot(storageRelease,requestedCarry)
    if not self:Alive() or not text(storageRelease,160) then error("Storage upgrade owner unavailable",0) end
    local owner=self.store:Current(self.ownerKey)
    local value=owner and owner.value
    if not value or value.account~=self.identity.account or value.place~=self.identity.place
        or value.version~=1 and value.version~=2 then error("Existing storage owner required",0) end
    local chain,previousCertificate={},nil
    if value.version==2 then previousCertificate,chain=self:Certificate(value) end
    if (value.storageRelease or value.release)~=storageRelease then error("Storage lineage changed",0) end
    local keys,why=self.store:ListKeys();if not keys then error(why or "Storage discovery failed",0) end
    if #keys>256 then error("Storage review key limit",0) end
    local canonical=self.store:Read(checkpointKey(self.identity,storageRelease))
    if not canonical then error("Canonical checkpoint required",0) end
    local cp=self:Checkpoint(canonical,storageRelease)
    if previousCertificate then self:RetainedSources(previousCertificate,storageRelease,cp) end
    local review={version=1,account=self.identity.account,place=self.identity.place,codeRelease=self.identity.release,
        storageRelease=storageRelease,owner={generation=owner.generation,sha256=self:Hash(owner.payload)},
        inventory={},legacy=self:Legacy(),requestHighwater=cp.requestHighwater,preserveOriginalEvidence=true}
    local sources={}
    for _,key in ipairs(keys) do
        local archive=key:sub(1,#self.archivePrefix)==self.archivePrefix
        if archive then self:ReadArchive(key) end
        if key:sub(1,#self.receiptPrefix)==self.receiptPrefix and key~=self.receiptKey and not chain[key] then
            error("Unreviewed storage lineage certificate",0)
        end
        if not archive and key:sub(1,#self.receiptPrefix)~=self.receiptPrefix then
            local current=self.store:Current(key)
            if not current then error("Discovered source unavailable",0) end
            if key==self.ownerKey and (current.generation~=owner.generation or current.payload~=owner.payload) then
                error("Storage owner changed during review",0)
            end
            if key==checkpointKey(self.identity,storageRelease) and not same(current.value,canonical) then
                error("Canonical checkpoint changed during review",0)
            end
            if key~=self.ownerKey and not self:CurrentScope(key,current.value,storageRelease,cp.requestHighwater) then
                local scope=keyScope(key)
                if not scope then error("Unsupported storage owner requires typed review",0) end
                if scope.account==self.identity.account and scope.place==self.identity.place then
                    if scope.family~="checkpoint" or scope.suffix~="" then error("Storage owner requires typed review",0) end
                    local sourceCP=self:Checkpoint(current.value,scope.release)
                    if scope.release~=storageRelease then
                        if #sourceCP:Records()>0 or (current.value.requestHighwater or 0)>cp.requestHighwater then
                            error("Foreign custody or request highwater requires typed carry",0)
                        end
                        for field,child in pairs(current.value) do
                            if field~="version" and field~="records" and field~="requestHighwater" then
                                if field=="familyClaimUsage" and type(child)=="table" and type(child.weeks)=="table" and next(child.weeks)==nil then
                                elseif field=="familyContributionUsage" and sourceCP.familyContributionUsage then
                                    for _,lane in pairs(sourceCP.familyContributionUsage.lanes) do
                                        if lane.attempted~=0 or lane.spent~=0 then error("Foreign Family allowance requires typed carry",0) end
                                    end
                                elseif type(child)~="number" or child~=0 then error("Foreign allowance requires typed carry",0) end
                            end
                        end
                    end
                end
            end
            review.inventory[#review.inventory+1]={key=key,generation=current.generation,sha256=self:Hash(current.payload)}
            sources[#sources+1]={key=key,generation=current.generation,payload=current.payload}
        end
    end
    local carryReview,carrySources
    if previousCertificate and previousCertificate.review.carryReview then
        self:AdoptCarry(previousCertificate,storageRelease,cp)
        carryReview,carrySources=previousCertificate.review.carryReview,previousCertificate.carrySources
    else
        local carry=self:Carry(requestedCarry,storageRelease)
        if carry then
            if type(carry.Preview)~="function" or type(carry.Verify)~="function" then error("Typed carry reviewer unavailable",0) end
            carryReview,carrySources=carry:Preview(cp)
            if type(carryReview)~="table" or type(carrySources)~="table" then error(carrySources or "Typed carry preview failed",0) end
            local valid,reason=carry:Verify(carryReview,cp,true)
            if valid~=true then error(reason or "Typed carry source changed",0) end
        end
    end
    review.carryReview=carryReview
    return review,sources,carrySources
end
function Methods:Preview(storageRelease)
    local ok,review=pcall(self.Snapshot,self,storageRelease)
    if not ok then return nil,tostring(review) end
    return review,nil
end
function Methods:Commit(review)
    local writerKey=self.deps.directory..":"..self.ownerKey
    if self.busy or writers[writerKey] then return nil,"Storage upgrade already in progress" end
    writers[writerKey]=self
    self.busy=true
    local ok,result=pcall(function()
        if type(review)~="table" then error("Exact storage review required",0) end
        local current,sources,carrySources=self:Snapshot(review.storageRelease,review.carryReview)
        if not same(current,review) then error("Storage review changed",0) end
        local certificate={version=1,review=current,sources={},carrySources=carrySources and {} or nil}
        for index,row in ipairs(sources) do
            certificate.sources[index]=self:Archive(row,"canonical",self.deps.directory.."/checkpoints")
        end
        for index,row in ipairs(carrySources or {}) do
            certificate.carrySources[index]=self:Archive(row,"carry",current.carryReview.sourceDirectory)
        end
        local existing=self.store:Current(self.receiptKey)
        if existing and not same(existing.value,certificate) then error("Storage upgrade certificate already differs",0) end
        if not existing then
            if self.store:Write(self.receiptKey,certificate)~=true then error("Storage certificate write unconfirmed",0) end
            existing=self.store:Current(self.receiptKey)
        end
        if not existing or not same(existing.value,certificate) then error("Storage certificate readback failed",0) end
        local latest=self:Snapshot(review.storageRelease,review.carryReview)
        if not same(latest,current) or not self:Alive() then error("Storage sources changed before adoption",0) end
        local cp=self:Checkpoint(self.store:Read(checkpointKey(self.identity,review.storageRelease)),review.storageRelease)
        local materialized={review=current,carrySources=carrySources}
        local guard,floor=self:AdoptCarry(materialized,review.storageRelease,cp)
        if not self:Alive() then error("Storage owner changed before adoption",0) end
        local owner={version=2,account=self.identity.account,place=self.identity.place,release=self.identity.release,
            storageRelease=review.storageRelease,receiptKey=self.receiptKey,receiptHash=self:Hash(existing.payload),
            receiptGeneration=existing.generation}
        if self.store:Write(self.ownerKey,owner)~=true then error("Storage owner write unconfirmed",0) end
        local stored=self.store:Read(self.ownerKey)
        if not same(stored,owner) or not self:Alive() then error("Storage owner readback failed",0) end
        return self:Result(review.storageRelease,guard,floor)
    end)
    if writers[writerKey]==self then writers[writerKey]=nil end
    self.busy=false
    return ok and result or nil,not ok and tostring(result) or nil
end
-- New rows created by the authorized code still belong to the same data lineage.
-- Their own producers validate full state on construction; this boundary refuses
-- foreign/unknown keys instead of treating a new directory entry as a fresh scope.
-- The second result marks only mutable main ledgers, never append-only receipts.
function Methods:CurrentScope(key,data,storageRelease,highwater)
    if type(data)~="table" then return false end
    if key:match("^idle%-mafia%-ember:adapter%-unsent:v1:") then
        if data.version~=1 or data.account~=self.identity.account or data.place~=self.identity.place
            or data.release~=storageRelease or not integer(data.requestId,1) or data.requestId>highwater then return false end
        local expected="idle-mafia-ember:adapter-unsent:v1:"
            ..self:Hash(checkpointKey(self.identity,storageRelease))..":"..string.format("%.0f",data.requestId)
        local decoded=self.deps.modules.PendingAction.Decode(data.recovery)
        local proposal=decoded and decoded.proposal
        return key==expected and proposal~=nil and proposal.account==data.account and proposal.place==data.place
            and proposal.release==data.release and proposal.requestId==data.requestId
    end
    if key:match("^idle%-mafia%-ember:crew%-replacement:v1:") then
        local scope=data.scope
        if type(scope)~="table" or scope.account~=self.identity.account or scope.place~=self.identity.place
            or scope.release~=storageRelease or data.schema~=1 or not integer(data.generation,1) then return false end
        local expected="idle-mafia-ember:crew-replacement:v1:"..scope.account..":"..scope.place..":"..scope.release
        return key==expected or key==expected..":adapter-unsent:"..string.format("%.0f",data.generation),key==expected
    end
    local scope=keyScope(key)
    if not scope or not dataFamilies[scope.family] or scope.account~=self.identity.account
        or scope.place~=self.identity.place or scope.release~=storageRelease then return false end
    if scope.suffix~="" then
        local kind,encoded=scope.suffix:match("^:(unsent):(%d+)$")
        if not kind then kind,encoded=scope.suffix:match("^:(rejected):(%d+)$") end
        local generation=tonumber(encoded)
        local tx=data.transaction
        return scope.family=="market-rent" and kind~=nil and integer(generation,1)
            and encoded==string.format("%.0f",generation) and integer(data.generation,1)
            and (kind=="unsent" and data.version==1 or kind=="rejected" and data.version==nil)
            and type(tx)=="table" and tx.preparedGeneration==generation and tx.account==scope.account
            and tx.place==scope.place and tx.release==scope.release
    end
    if scope.family=="checkpoint" then return self:Checkpoint(data,storageRelease)~=nil,true end
    if scope.family=="market-rent" then
        if data.version~=1 or not integer(data.generation,0) then return false end
        for _,field in ipairs({"listingAttempts","withdrawAttempts","flipListingAttempts","buyAttempts","buySpent"}) do
            if not integer(data[field],0) then return false end
        end
        return data.transaction==nil or type(data.transaction)=="table" and data.transaction.account==scope.account
            and data.transaction.place==scope.place and data.transaction.release==scope.release,true
    end
    if scope.family=="territory-recall" then
        return data.version==2 and integer(data.userId,1) and integer(data.generation,0)
            and integer(data.attempted,0) and integer(data.lastRequestId,0),true
    end
    if data.version~=1 or data.account~=scope.account or data.place~=scope.place or data.release~=scope.release then return false end
    if scope.family=="payouts" then
        return integer(data.claims,0) and integer(data.gold,0) and integer(data.lastRequestId,0) and type(data.recent)=="table",true
    end
    return scope.family=="player-fights" and integer(data.fights,0) and integer(data.wins,0)
        and integer(data.cash,0) and integer(data.stamina,0) and integer(data.lastRequestId,0)
        and type(data.recent)=="table" and type(data.highValue)=="table",true
end
-- Mutable canonical ledgers may advance under their existing producer guards.
-- Foreign sources and numbered known-unsent/rejection receipts stay immutable.
function Methods:RetainedSources(certificate,storageRelease,cp)
    local inventory={}
    if cp.requestHighwater<certificate.review.requestHighwater then error("Request highwater regressed",0) end
    for _,row in ipairs(certificate.review.inventory) do
        inventory[row.key]=true
        if row.key~=self.ownerKey and row.key~=checkpointKey(self.identity,storageRelease) then
            local current=self.store:Current(row.key)
            if not current then error("Retained source unavailable",0) end
            if not integer(current.generation,row.generation) or current.generation==row.generation
                and self:Hash(current.payload)~=row.sha256 then error("Retained source generation regressed or changed",0) end
            local valid,mutable=self:CurrentScope(row.key,current.value,storageRelease,cp.requestHighwater)
            if not (valid and mutable) and (current.generation~=row.generation or self:Hash(current.payload)~=row.sha256) then
                error("Retained foreign or immutable source changed",0)
            end
        end
    end
    return inventory
end
function Methods:Open()
    local ok,result=pcall(function()
        if not self:Alive() then error("Storage owner unavailable",0) end
        local ownerSlot=self.store:Current(self.ownerKey)
        local owner=ownerSlot and ownerSlot.value
        if type(owner)~="table" or owner.release~=self.identity.release then error("Code release requires explicit storage review",0) end
        local certificate,chain=self:Certificate(owner)
        if not same(certificate.review.legacy,self:Legacy()) then error("Legacy source changed after upgrade",0) end
        local cp=self:Checkpoint(self.store:Read(checkpointKey(self.identity,owner.storageRelease)),owner.storageRelease)
        local inventory=self:RetainedSources(certificate,owner.storageRelease,cp)
        local keys,why=self.store:ListKeys();if not keys then error(why or "Storage discovery failed",0) end
        for _,key in ipairs(keys) do
            if not inventory[key] and not chain[key] then
                local data=self.store:Read(key)
                if key:sub(1,#self.archivePrefix)==self.archivePrefix then self:ReadArchive(key)
                elseif not self:CurrentScope(key,data,owner.storageRelease,cp.requestHighwater) then error("New storage owner requires typed review",0) end
            end
        end
        local guard,floor=self:AdoptCarry(certificate,owner.storageRelease,cp)
        local finalOwner=self.store:Current(self.ownerKey)
        if not finalOwner or finalOwner.generation~=ownerSlot.generation or finalOwner.payload~=ownerSlot.payload
            or not self:Alive() then error("Storage owner changed",0) end
        return self:Result(owner.storageRelease,guard,floor)
    end)
    return ok and result or nil,not ok and tostring(result) or nil
end
return StorageUpgrade
