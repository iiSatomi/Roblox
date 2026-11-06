-- Durable tab-owned Market custody. This module never invokes a Remote.
local MarketTransactions = {}
local Methods = {}
Methods.__index = Methods
local writers = {}
local MAX = 9007199254740991

local function integer(value, minimum, maximum)
    return type(value) == "number" and value == value
        and value % 1 == 0 and value >= minimum
        and value <= maximum
end

local function finite(value)
    return type(value) == "number" and value == value
        and value >= 0 and value < math.huge
end

local function key(scope)
    return "idle-mafia-ember:market-rent:v1:"
        .. #scope.account .. ":" .. scope.account
        .. #scope.place .. ":" .. scope.place
        .. #scope.release .. ":" .. scope.release
end

local function copy(record)
    if not record then return nil end
    local nodes, seen = 0, {}
    local function clone(value, depth)
        nodes = nodes + 1
        if nodes > 24000 or depth > 8 then error("Record too large") end
        if type(value) == "table" then
            if seen[value] then error("Cyclic record") end
            seen[value] = true
            local result, rows = {}, 0
            for field, child in pairs(value) do
                rows = rows + 1
                if rows > 10000 or type(field) ~= "string"
                    or #field == 0 or #field > 256 then
                    error("Invalid record key")
                end
                result[field] = clone(child, depth + 1)
            end
            seen[value] = nil
            return result
        elseif type(value) == "string" then
            if #value > 256 then error("Record string too large") end
        elseif type(value) == "number" then
            if not finite(value) then error("Invalid record number") end
        elseif type(value) ~= "boolean" then
            error("Invalid record value")
        end
        return value
    end
    local ok, result = pcall(clone, record, 0)
    return ok and result or nil
end

local function text(value, maximum)
    return type(value) == "string" and #value > 0 and #value <= maximum
end
local function equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for field, value in pairs(a) do if not equal(value, b[field]) then return false end end
    for field in pairs(b) do if a[field] == nil then return false end end
    return true
end

local function flipList(record)
    return type(record)=="table" and record.kind=="list" and type(record.origin)=="table" and record.origin.kind=="buy"
end
local function rejectedOrigin(record)
    local origin=copy(record.origin)
    if origin then origin.listAttempts=record.listAttempts end
    return origin
end

-- Earlier code could persist observed custody before checking the callback.
-- Keep that exact record readable, but never treat a nonterminal observed
-- receipt (including an acquisition origin) as permission to release custody.
local function uncertainObserved(record)
    if type(record) ~= "table" then return false end
    if record.stage == "observed" then
        local reply = record.reply
        if reply ~= nil then
            if type(reply) ~= "table" or reply.ok ~= true or reply.pending == true
                or reply.code == "pending" or reply.code == "busy"
                or reply.code == "rate_limited" or reply.code == "presence" then return true end
        elseif record.actionKey ~= nil then return true end
    end
    return uncertainObserved(record.origin)
end

local function header(record, scope)
    return type(record) == "table"
        and type(record.session) == "string"
        and #record.session > 0 and #record.session <= 200
        and record.account == scope.account
        and record.place == scope.place
        and record.release == scope.release
        and integer(record.revision, 0, 9007199254740991)
        and finite(record.serverNow)
end

local function listingsValid(record)
    if not integer(record.size, 0, 100)
        or type(record.listings) ~= "table" then
        return false
    end
    local count = 0
    for id, row in pairs(record.listings) do
        count = count + 1
        if count > 100 or type(id) ~= "string"
            or #id < 1 or #id > 160
            or type(row) ~= "table"
            or type(row.state) ~= "string"
            or #row.state < 1 or #row.state > 40
            or type(row.item) ~= "string"
            or #row.item < 1 or #row.item > 120
            or not integer(row.indexed, 0, 1000000000)
            or not integer(row.price, 1, 9999999)
            or not integer(row.qty, 1, 999)
            or not integer(row.left, 0, row.qty)
            or not integer(row.createdAt, 0, 9007199254740991)
            or not integer(row.total, 0, 1000000000)
            or not integer(row.free, 0, row.total) then
            return false
        end
    end
    return count == record.size
end

local function intermediateValid(record, scope)
    local b = record.baseline
    if not header(b, scope) or b.session ~= record.session
        or b.revision ~= record.revision or b.serverNow ~= record.serverNow
        or not text(b.itemId, 120) or b.itemId == "gold_bar"
        or not integer(record.expectedAsk, 2, 9999999)
        or not integer(record.listAttempts,0,20) then return false end
    if record.stage == "observed" then
        if not text(record.confirmedSession, 200)
            or not integer(record.confirmedRevision, 0, 9007199254740991)
            or not finite(record.confirmedServerNow)
            or record.confirmedServerNow < record.serverNow
            or (record.confirmedSession == record.session
                and record.confirmedRevision <= record.revision)
            or (record.confirmedSession ~= record.session
                and record.confirmedServerNow <= record.serverNow) then
            return false
        end
    elseif record.confirmedSession ~= nil
        or record.confirmedRevision ~= nil
        or record.confirmedServerNow ~= nil then return false end
    if record.kind == "buy" then
        return record.plannedQuantity == 1
            and (text(b.listingId, 160)
                or integer(b.listingId, 1, 9007199254740991))
            and integer(b.price, 1, 9999999)
            and integer(b.gold, b.price, 1000000000)
            and integer(b.boundGold, 0, 1000000000)
            and integer(b.item, 0, 999999999)
            and integer(b.boundItem, 0, 1000000000)
            and listingsValid(b)
    end
    if record.kind ~= "withdraw"
        or not integer(b.quantity, 1, 999)
        or not integer(record.plannedQuantity, b.quantity, 999)
        or not integer(b.loose, 0, 1000000000 - b.quantity)
        or record.plannedQuantity > b.loose + b.quantity
        or not integer(b.collected, b.quantity, 1000000000)
        or not integer(b.floor, 0, 1000000000)
        or not integer(b.total, b.quantity + b.floor, 1000000000) then
        return false
    end
    for _, field in ipairs({ "bound", "collectedBound", "gold", "boundGold" }) do
        if not integer(b[field], 0, 1000000000) then return false end
    end
    local total = b.collected + b.collectedBound
    for _, field in ipairs({ "looseVariants", "boundVariants" }) do
        if type(b[field]) ~= "table" then return false end
        local rows = 0
        for id, value in pairs(b[field]) do
            rows = rows + 1
            if rows > 10000 or not text(id, 256)
                or id:sub(1, #b.itemId + 1) ~= b.itemId .. "@"
                or not integer(value, 0, 1000000000) then return false end
            total = total + value
        end
    end
    return total == b.total
end

local function runtimeBinding(record)
    if type(record) ~= "table" then return false end
    if record.actionKey == nil and record.sourceKey == nil and record.preparedGeneration == nil then return true end
    if record.reply ~= nil then
        if type(record.reply) ~= "table" or (record.reply.ok ~= nil and type(record.reply.ok) ~= "boolean")
            or (record.reply.pending ~= nil and type(record.reply.pending) ~= "boolean")
            or (record.reply.code ~= nil and not text(record.reply.code, 120))
            or (record.reply.moved ~= nil and not integer(record.reply.moved, 0, 999)) then return false end
        for field in pairs(record.reply) do
            if field ~= "ok" and field ~= "pending" and field ~= "code" and field ~= "moved" then return false end
        end
    end
    return (record.kind == "list" or record.kind == "withdraw" or record.kind == "buy") and text(record.actionKey, 240)
        and type(record.sourceKey) == "string" and #record.sourceKey == 64
        and record.sourceKey:match("^[%x]+$") ~= nil
        and integer(record.preparedGeneration, 1, MAX)
end

local function valid(record, scope)
    if not runtimeBinding(record) or not header(record, scope)
        or (record.stage ~= "prepared" and record.stage ~= "sent"
            and record.stage ~= "observed") then return false end
    if record.kind == "rent" then
        return integer(record.shopUntil, 0, 9007199254740991)
            and integer(record.loose, 0, 1000000000)
            and integer(record.bound, 0, 1000000000)
            and integer(record.cost, 1, 1000)
            and integer(record.durationSeconds, 3600, 2592000)
    end
    if record.kind == "withdraw" or record.kind == "buy" then
        return intermediateValid(record, scope)
    end
    if record.kind ~= "list" or not text(record.itemId, 120)
        or not integer(record.quantity, 1, 999)
        or not integer(record.ask, 1, 9999999)
        or not integer(record.loose, record.quantity, 1000000000)
        or not integer(record.bound, 0, 1000000000)
        or not listingsValid(record) then return false end
    if record.origin == nil then return record.listAttempts == nil end
    local origin = record.origin
    if not header(origin, scope) or origin.stage ~= "observed"
        or not intermediateValid(origin, scope)
        or record.listAttempts ~= origin.listAttempts + 1
        or record.itemId ~= origin.baseline.itemId
        or record.quantity ~= origin.plannedQuantity
        or record.ask ~= origin.expectedAsk then return false end
    local b = origin.baseline
    return record.loose == (origin.kind == "withdraw"
            and b.loose + b.quantity or b.item + 1)
        and record.bound == (origin.kind == "withdraw" and b.bound or b.boundItem)
        and record.serverNow >= origin.confirmedServerNow
        and record.serverNow - origin.confirmedServerNow <= 3600
end

function MarketTransactions.new(storage, scope, listEvidence, withdrawEvidence, buyEvidence)
    if type(storage) ~= "table" or storage.strictRecovery ~= true
        or type(storage.Read) ~= "function"
        or type(storage.Write) ~= "function"
        or type(scope) ~= "table" then
        return nil, "Strict Market transaction storage required"
    end
    for _, field in ipairs({ "account", "place", "release" }) do
        if type(scope[field]) ~= "string"
            or #scope[field] == 0 or #scope[field] > 200 then
            return nil, "Invalid Market transaction identity"
        end
    end
    local own = { account = scope.account,
        place = scope.place, release = scope.release }
    for _, entry in ipairs({ { listEvidence }, { withdrawEvidence }, { buyEvidence } }) do
        local evidence = entry[1]
        if evidence ~= nil and (type(evidence) ~= "table"
            or type(evidence.capture) ~= "function"
            or type(evidence.observe) ~= "function") then
            return nil, "Invalid Market transaction evidence"
        end
    end
    local storageKey = key(own)
    if writers[storageKey] then return nil, "Market transaction save in flight" end
    local ok, value = pcall(storage.Read, storage, storageKey)
    if not ok then return nil, "Market transaction read failed" end
    if value ~= nil then
        value = copy(value)
        if not value then return nil, "Corrupt Market transaction" end
    end
    local chargedBuy=type(value)=="table" and type(value.transaction)=="table" and value.transaction
    if chargedBuy and chargedBuy.kind=="list" then chargedBuy=chargedBuy.origin end
    if type(chargedBuy)~="table" or chargedBuy.kind~="buy" or chargedBuy.actionKey==nil
        or chargedBuy.stage=="prepared" then chargedBuy=nil end
    if value ~= nil and (type(value) ~= "table"
        or value.version ~= 1
        or (value.flipListingAttempts~=nil and not integer(value.flipListingAttempts,0,400))
        or (flipList(value.transaction) and value.transaction.actionKey~=nil and value.transaction.stage~="prepared"
            and (not integer(value.transaction.listAttempts,1,20)
                or not integer(value.flipListingAttempts,value.transaction.listAttempts,400)))
        or ((value.buyAttempts==nil)~=(value.buySpent==nil))
        or (value.buyAttempts~=nil and not integer(value.buyAttempts,0,20))
        or (value.buySpent~=nil and not integer(value.buySpent,0,1000000000))
        or (value.buyAttempts~=nil and value.buySpent~=nil and (value.buySpent<value.buyAttempts
            or value.buyAttempts==0 and value.buySpent~=0))
        or (chargedBuy and (not integer(value.buyAttempts,1,20)
            or type(chargedBuy.baseline)~="table" or not integer(chargedBuy.baseline.price,1,9999999)
            or not integer(value.buySpent,chargedBuy.baseline.price,1000000000)))
        or (type(value.transaction)=="table" and value.transaction.kind=="buy" and value.transaction.actionKey~=nil
            and (not integer(value.buyAttempts,0,20) or not integer(value.buySpent,0,1000000000)))
        or (value.withdrawAttempts ~= nil and not integer(value.withdrawAttempts, 0, 20))
        or (type(value.transaction)=="table" and value.transaction.actionKey~=nil and value.transaction.kind=="withdraw"
            and (not integer(value.withdrawAttempts,0,20) or value.transaction.stage~="prepared" and value.withdrawAttempts<1))
        or (type(value.transaction) == "table" and value.transaction.actionKey ~= nil
            and (not integer(value.listingAttempts, 0, 20)
                or not integer(value.generation, 1, MAX)
                or (value.transaction.stage == "prepared" and value.transaction.preparedGeneration ~= value.generation)
                or (value.transaction.stage ~= "prepared" and (not integer(value.transaction.preparedGeneration, 1, MAX)
                    or value.transaction.preparedGeneration >= value.generation))))
        or (value.listingAttempts ~= nil and not integer(value.listingAttempts, 0, 20))
        or (value.listingAttempts ~= nil and type(value.transaction) == "table"
            and value.transaction.kind == "list" and not flipList(value.transaction) and value.transaction.stage ~= "prepared"
            and value.listingAttempts < 1)
        or (value.generation ~= nil and not integer(value.generation, 0, MAX))
        or (value.transaction ~= nil
            and not valid(value.transaction, own))) then
        return nil, "Corrupt Market transaction"
    end
    return setmetatable({ storage = storage, scope = own,
        key = storageKey, expected = value and copy(value) or nil,
        generation = value and value.generation or 0, closed = false,
        flipListingAttempts=value and value.flipListingAttempts or 0,
        buyAttempts=value and value.buyAttempts or 0, buySpent=value and value.buySpent or 0,
        listingAttempts = value == nil and 0 or value.listingAttempts,
        withdrawAttempts = value == nil and 0 or value.withdrawAttempts,
        listEvidence = listEvidence,
        withdrawEvidence = withdrawEvidence, buyEvidence = buyEvidence,
        transaction = value and copy(value.transaction) or nil }, Methods), nil
end

function Methods:Active()
    return copy(self.transaction)
end
function Methods:Close() self.closed = true end

-- Intermediate acquisitions keep their intended loose output until listing is
-- observed. No continuation exemption is invented for old records without keys.
function Methods:ReservationClaims()
    local record = self.transaction
    if record == nil then return nil end
    if not valid(record, self.scope) then return nil, "Market custody invalid" end
    local held = uncertainObserved(record)
    local observed = record.stage == "observed" and not held
    if observed and record.kind ~= "buy" and record.kind ~= "withdraw" then return nil end
    local claims = {members = {}, items = {}, funds = {}, allCrew = false, allItems = false}
    local feature = record.kind == "rent" and "marketRent" or "marketSell"
    if record.kind == "rent" then
        claims.items["L:gold_bar"] = record.cost
    elseif record.kind == "list" then
        claims.items["L:" .. record.itemId] = record.quantity
    elseif record.kind == "buy" then
        feature = "marketFlip"
        claims.items["L:" .. record.baseline.itemId] = 1
        if not observed then
            claims.items["L:gold_bar"] = (claims.items["L:gold_bar"] or 0) + record.baseline.price
        end
    else
        claims.items["L:" .. record.baseline.itemId] = record.plannedQuantity
    end
    local actionKey=record.actionKey
    if record.kind=="list" and record.origin and record.origin.kind=="buy" then feature="marketFlip" end
    if record.kind=="buy" and record.actionKey~=nil and observed then
        actionKey="market-flip-list:"..record.sourceKey..":"..tostring(self.generation+1)..":"..record.baseline.itemId
    end
    if record.kind=="withdraw" and record.actionKey~=nil then
        if not observed then claims.allItems=true
        else actionKey="market-list:"..record.sourceKey..":"..tostring(self.generation+1)..":"..record.baseline.itemId end
    end
    local origin = record.origin
    if held and type(origin) == "table" and uncertainObserved(origin) then
        local itemId = origin.baseline.itemId
        local quantity = origin.kind == "buy" and 1 or origin.plannedQuantity
        claims.items["L:" .. itemId] = math.max(claims.items["L:" .. itemId] or 0, quantity)
        if origin.kind == "buy" then claims.items["L:gold_bar"] = origin.baseline.price
        else claims.allItems = true end
    end
    return {account = self.scope.account, place = self.scope.place,
        release = self.scope.release, feature = feature, actionKey = actionKey, claims = claims}, nil
end

local function persist(self, nextRecord, listingAttempts, withdrawAttempts, buyAttempts, buySpent, flipListingAttempts)
    if self.closed then return false, "Market transaction owner closed" end
    if writers[self.key] then return false, "Market transaction save in flight" end
    if self.generation >= MAX then return false, "Market transaction generations exhausted" end
    local saved = copy(nextRecord)
    if nextRecord ~= nil and (not saved or not valid(saved, self.scope)) then
        return false, "Invalid Market transaction record"
    end
    writers[self.key] = self
    if listingAttempts == nil then listingAttempts = self.listingAttempts end
    if withdrawAttempts == nil then withdrawAttempts = self.withdrawAttempts end
    if flipListingAttempts==nil then flipListingAttempts=self.flipListingAttempts end
    if buyAttempts==nil then buyAttempts=self.buyAttempts end
    if buySpent==nil then buySpent=self.buySpent end
    local nextEnvelope = {flipListingAttempts=flipListingAttempts,buyAttempts=buyAttempts,buySpent=buySpent,version = 1, transaction = copy(saved), generation = self.generation + 1,
        listingAttempts = listingAttempts, withdrawAttempts = withdrawAttempts}
    local ok, result = pcall(function()
        local raw = self.storage:Read(self.key)
        local current = raw ~= nil and copy(raw) or nil
        if (raw ~= nil and current == nil) or not equal(current, self.expected) or self.closed then return false end
        return self.storage:Write(self.key, nextEnvelope)
    end)
    if writers[self.key] == self then writers[self.key] = nil end
    if not ok or result ~= true then
        return false, "Market transaction persistence failed"
    end
    self.flipListingAttempts=flipListingAttempts
    self.buyAttempts,self.buySpent=buyAttempts,buySpent
    self.transaction = saved
    self.listingAttempts, self.withdrawAttempts = listingAttempts, withdrawAttempts
    self.expected, self.generation = copy(nextEnvelope), nextEnvelope.generation
    self.listingProof = nil
    if self.closed then return false, "Market owner closed during persistence" end
    return true, nil
end

-- Local recovery primitives only. A future UI must additionally require pause,
-- no active/pending generic request, and one-use expiring confirmation.
function Methods:PreparedReview()
    if self.closed or writers[self.key] or not self.transaction or uncertainObserved(self.transaction)
        or self.transaction.stage ~= "prepared" then
        return nil, "No current unsent Market preparation"
    end
    return {account = self.scope.account, place = self.scope.place, release = self.scope.release,
        generation = self.generation, transaction = copy(self.transaction)}, nil
end
function Methods:DiscardPrepared(expected)
    local current, reason = self:PreparedReview()
    if not current or type(expected) ~= "table" or not equal(current, expected) then
        return false, reason or "Prepared Market review changed"
    end
    return persist(self, nil) -- Exact-envelope comparison also fences another owner.
end

local function state(raw, scope)
    local native = type(raw) == "table" and raw.native
    local market = type(native) == "table" and native.market
    local loose = type(native) == "table" and native.inventory
    local bound = type(native) == "table" and native.inventoryBound
    if type(raw) ~= "table" or raw.account ~= scope.account
        or raw.place ~= scope.place or raw.release ~= scope.release
        or type(raw.session) ~= "string" or #raw.session == 0
        or not integer(raw.revision, 0, 9007199254740991)
        or type(native) ~= "table" or native.fullSync ~= true
        or not finite(native.serverNow)
        or type(market) ~= "table"
        or not integer(market.shopUntil, 0, 9007199254740991)
        or type(loose) ~= "table" or type(bound) ~= "table" then
        return nil
    end
    local looseGold = loose.gold_bar
    local boundGold = bound.gold_bar
    if looseGold == nil then looseGold = 0 end
    if boundGold == nil then boundGold = 0 end
    if not integer(looseGold, 0, 1000000000)
        or not integer(boundGold, 0, 1000000000) then
        return nil
    end
    return { revision = raw.revision,
        session = raw.session,
        serverNow = native.serverNow,
        shopUntil = market.shopUntil,
        loose = looseGold, bound = boundGold }
end

function Methods:PrepareRent(proposal, before)
    if self.transaction then
        return false, "Unresolved Market rental exists"
    end
    local intent = type(proposal) == "table" and proposal.intent
    local beforeState = state(before, self.scope)
    if not beforeState or type(proposal) ~= "table"
        or proposal.feature ~= "marketRent"
        or proposal.account ~= self.scope.account
        or proposal.place ~= self.scope.place
        or proposal.release ~= self.scope.release
        or proposal.session ~= before.session
        or type(intent) ~= "table"
        or intent.kind ~= "marketRent" or intent.periods ~= 1
        or not integer(intent.cost, 1, 1000)
        or not integer(intent.durationSeconds, 3600, 2592000)
        or proposal.revision ~= beforeState.revision
        or beforeState.loose < intent.cost then
        return false, "Current one-period rental proof required"
    end
    return persist(self, { kind = "rent", stage = "prepared",
        session = before.session,
        account = self.scope.account, place = self.scope.place,
        release = self.scope.release,
        revision = beforeState.revision,
        serverNow = beforeState.serverNow,
        shopUntil = beforeState.shopUntil,
        loose = beforeState.loose, bound = beforeState.bound,
        cost = intent.cost,
        durationSeconds = intent.durationSeconds })
end

local function prepareOwnedList(self, proposal, before, runtime)
    if self.transaction then
        return false, "Unresolved Market transaction exists"
    end
    if type(self.listEvidence) ~= "table"
        or type(proposal) ~= "table"
        or proposal.feature ~= "marketSell"
        or (not runtime and proposal.preflightOnly ~= true)
        or proposal.account ~= self.scope.account
        or proposal.place ~= self.scope.place
        or proposal.release ~= self.scope.release then
        return false, "Current owned-listing evidence required"
    end
    local ok, baseline = pcall(self.listEvidence.capture,
        proposal, before)
    if not ok or type(baseline) ~= "table" then
        return false, "Current owned-listing custody required"
    end
    local record = { kind = "list", stage = "prepared",
        session = before.session,
        account = self.scope.account, place = self.scope.place,
        release = self.scope.release,
        revision = baseline.revision,
        serverNow = baseline.serverNow,
        itemId = baseline.itemId,
        quantity = baseline.quantity,
        ask = baseline.ask,
        loose = baseline.loose,
        bound = baseline.bound,
        size = baseline.size,
        listings = baseline.listings }
    if runtime then
        record.actionKey, record.sourceKey = proposal.actionKey, proposal.intent.sourceKey
        record.preparedGeneration = self.generation + 1
    end
    if not valid(record, self.scope) then
        return false, "Invalid owned-listing baseline"
    end
    return persist(self, copy(record))
end

function Methods:PrepareOwnedList(proposal, before)
    return prepareOwnedList(self, proposal, before, false)
end

function Methods:PrepareRuntimeOwnedList(proposal, before, maximum)
    local intent = type(proposal) == "table" and proposal.intent
    if not integer(self.listingAttempts, 0, 20) or not integer(maximum, 1, 20)
        or self.listingAttempts >= maximum or type(proposal) ~= "table"
        or not text(proposal.actionKey, 240) or type(intent) ~= "table"
        or type(intent.sourceKey) ~= "string" or #intent.sourceKey ~= 64
        or not intent.sourceKey:match("^[%x]+$")
        or type(proposal.resources) ~= "table"
        or proposal.resources[intent.itemId] ~= intent.quantity then
        return false, "Current bounded listing ownership required"
    end
    for id in pairs(proposal.resources) do
        if id ~= intent.itemId then return false, "Unexpected listing resource" end
    end
    return prepareOwnedList(self, proposal, before, true)
end

function Methods:AuthorizeRuntimeOwnedList(actionKey, generation, maximum, sourceKey)
    local record = self.transaction
    if self.closed or not record or record.kind ~= "list" or record.stage ~= "prepared"
        or record.actionKey ~= actionKey or record.sourceKey ~= sourceKey
        or record.preparedGeneration ~= generation or self.generation ~= generation
        or not integer(maximum, 1, 20) then
        return false, "Listing runtime authorization changed"
    end
    return self:MarkSending(maximum)
end

function Methods:RecordRuntimeReturn(actionKey, generation, reply)
    local record = self.transaction
    if self.closed or not record or record.stage ~= "sent" or (record.kind ~= "list" and record.kind ~= "withdraw" and record.kind ~= "buy")
        or not text(actionKey, 240) or not integer(generation, 1, MAX)
        or record.actionKey ~= actionKey or record.preparedGeneration ~= generation
        or type(reply) ~= "table" or (reply.ok ~= nil and type(reply.ok) ~= "boolean")
        or (reply.pending ~= nil and type(reply.pending) ~= "boolean")
        or (reply.code ~= nil and not text(reply.code, 120))
        or (reply.moved ~= nil and not integer(reply.moved,0,999)) then
        return false, "Listing return does not match sent ownership"
    end
    if record.reply ~= nil then return false, "Listing return already recorded" end
    local nextRecord = copy(record)
    nextRecord.reply = {ok = reply.ok, pending = reply.pending, code = reply.code, moved=reply.moved}
    return persist(self, nextRecord)
end

local function runtimeUnsentFact(scope, envelope)
    local record = type(envelope) == "table" and envelope.transaction
    if type(envelope) ~= "table" or envelope.version ~= 1
        or not integer(envelope.generation, 1, MAX) or not integer(envelope.listingAttempts, 0, 20)
        or not valid(record, scope) or (record.kind ~= "list" and record.kind ~= "withdraw" and record.kind ~= "buy") or not text(record.actionKey, 240)
        or record.reply ~= nil or not integer(record.preparedGeneration, 1, MAX)
        or (record.stage ~= "prepared" and record.stage ~= "sent") then return nil end
    if record.stage == "prepared" and envelope.generation ~= record.preparedGeneration then return nil end
    local attempts=flipList(record) and envelope.flipListingAttempts or record.kind=="buy" and envelope.buyAttempts or record.kind=="withdraw" and envelope.withdrawAttempts or envelope.listingAttempts
    if not integer(attempts,0,20) then return nil end
    if record.stage == "sent" and (envelope.generation ~= record.preparedGeneration + 1 or attempts<1) then return nil end
    return {version = 1, generation = envelope.generation,
        listingAttempts = envelope.listingAttempts, withdrawAttempts=envelope.withdrawAttempts,
        flipListingAttempts=envelope.flipListingAttempts,buyAttempts=envelope.buyAttempts,buySpent=envelope.buySpent,transaction = copy(record)}
end

-- Adapter evidence only. Intentionally allowed after Close; never changes the main file.
function Methods:RecordRuntimeUnsent(actionKey, preparedGeneration)
    if not text(actionKey, 240) or not integer(preparedGeneration, 1, MAX) then
        return false, "Unsent listing identity required"
    end
    local ok, saved = pcall(self.storage.Read, self.storage, self.key)
    local fact = ok and runtimeUnsentFact(self.scope, saved)
    if not fact or fact.transaction.actionKey ~= actionKey
        or fact.transaction.preparedGeneration ~= preparedGeneration then
        return false, "Durable listing no longer matches unsent callback"
    end
    local factKey = self.key .. ":unsent:" .. tostring(preparedGeneration)
    local read, existing = pcall(self.storage.Read, self.storage, factKey)
    if not read or (existing ~= nil and not equal(existing, fact)) then return false, "Unsent fact changed" end
    if existing ~= nil then return true, nil end
    local wrote, result = pcall(self.storage.Write, self.storage, factKey, fact)
    return wrote and result == true, (not wrote or result ~= true) and "Unsent evidence write failed" or nil
end

function Methods:RuntimeUnsentReview()
    if self.closed or writers[self.key] or uncertainObserved(self.transaction) then return nil, "Listing owner unavailable" end
    local expected = runtimeUnsentFact(self.scope, self.expected)
    if not expected or self.generation ~= expected.generation or not equal(self.transaction, expected.transaction) then
        return nil, "No current runtime listing for unsent review"
    end
    local read, current = pcall(self.storage.Read, self.storage, self.key)
    if not read or not equal(current, self.expected) then return nil, "Listing custody changed" end
    local ok, fact = pcall(self.storage.Read, self.storage,
        self.key .. ":unsent:" .. tostring(expected.transaction.preparedGeneration))
    if not ok or not equal(fact, expected) then return nil, "Definite-unsent evidence unavailable" end
    return copy(expected), nil
end

function Methods:RuntimeUnsentReceipt(actionKey, preparedGeneration)
    if self.closed or not text(actionKey, 240)
        or not integer(preparedGeneration, 1, MAX) then return nil end
    local ok, saved = pcall(self.storage.Read, self.storage,
        self.key .. ":unsent:" .. tostring(preparedGeneration))
    local fact = ok and runtimeUnsentFact(self.scope, saved)
    if not fact or uncertainObserved(fact.transaction) or fact.transaction.actionKey ~= actionKey or fact.transaction.preparedGeneration ~= preparedGeneration
        or self.generation ~= fact.generation + 1
        or not equal(self.transaction,fact.transaction.origin) then return nil end
    local attempted,withdrawn=fact.listingAttempts,fact.withdrawAttempts
    local bought,spent=fact.buyAttempts,fact.buySpent
    local flipped=fact.flipListingAttempts
    if fact.transaction.stage=="sent" then
        if flipList(fact.transaction) then flipped=flipped-1
        elseif fact.transaction.kind=="buy" then bought=bought-1;spent=spent-fact.transaction.baseline.price
        elseif fact.transaction.kind=="withdraw" then withdrawn=withdrawn-1 else attempted=attempted-1 end
    end
    if self.listingAttempts~=attempted or self.withdrawAttempts~=withdrawn
        or self.buyAttempts~=bought or self.buySpent~=spent or self.flipListingAttempts~=flipped then return nil end
    local read, current = pcall(self.storage.Read, self.storage, self.key)
    if not read or not equal(current, self.expected) then return nil end
    return copy(fact)
end

function Methods:ReleaseRuntimeUnsent(review)
    local current, reason = self:RuntimeUnsentReview()
    if not current or type(review) ~= "table" or not equal(review, current) then
        return false, reason or "Unsent listing review changed"
    end
    local attempts,withdrawn=current.listingAttempts,current.withdrawAttempts
    local bought,spent=current.buyAttempts,current.buySpent
    local flipped=current.flipListingAttempts
    if current.transaction.stage=="sent" then
        if flipList(current.transaction) then flipped=flipped-1
        elseif current.transaction.kind=="buy" then bought=bought-1;spent=spent-current.transaction.baseline.price
        elseif current.transaction.kind=="withdraw" then withdrawn=withdrawn-1 else attempts=attempts-1 end
    end
    return persist(self,current.transaction.origin,attempts,withdrawn,bought,spent,flipped)
end

-- Local review primitives; the UI/runtime must additionally enforce pause and no pending broker action.
function Methods:RejectedRuntimeReview(raw)
    local record = self.transaction
    if self.closed or writers[self.key] or not record or uncertainObserved(record) or record.stage ~= "sent"
        or not text(record.actionKey, 240) or type(self.listEvidence) ~= "table"
        or type(self.listEvidence.evaluate) ~= "function" or type(record.reply) ~= "table"
        or record.reply.ok ~= false then return nil, "No exactly rejected runtime listing" end
    local proposal = {session = record.session, account = record.account, place = record.place,
        release = record.release, revision = record.revision, feature = "marketSell",
        intent = {kind = "marketList", itemId = record.itemId, quantity = record.quantity, ask = record.ask}}
    local ok, outcome
    if record.kind=="buy" and type(self.buyEvidence)=="table" and type(self.buyEvidence.evaluateStored)=="function" then
        ok,outcome=pcall(self.buyEvidence.evaluateStored,record.baseline,raw,record.reply)
    elseif record.kind=="withdraw" and type(self.withdrawEvidence)=="table" and type(self.withdrawEvidence.evaluateStored)=="function" then
        ok,outcome=pcall(self.withdrawEvidence.evaluateStored,record.baseline,raw,record.reply)
    elseif type(self.listEvidence.evaluateStored) == "function" then
        ok, outcome = pcall(self.listEvidence.evaluateStored, record, raw, record.reply)
    else ok, outcome = pcall(self.listEvidence.evaluate, proposal, proposal, raw, record.reply, record) end
    if not ok or outcome ~= "rejected" then return nil, "Listing rejection custody is uncertain" end
    return {account = self.scope.account, place = self.scope.place, release = self.scope.release,
        generation = self.generation, transaction = copy(record),
        snapshot = {session = raw.session, revision = raw.revision, capturedAt = raw.capturedAt,
            serverNow = raw.native.serverNow}}, nil
end

function Methods:ReleaseRejectedRuntimeList(review, raw)
    local current, reason = self:RejectedRuntimeReview(raw)
    if not current or type(review) ~= "table" or not equal(current, review) then
        return false, reason or "Listing rejection review changed"
    end
    local fact={generation=self.generation,transaction=copy(current.transaction),
        listingAttempts=self.listingAttempts,withdrawAttempts=self.withdrawAttempts,buyAttempts=self.buyAttempts,buySpent=self.buySpent,flipListingAttempts=self.flipListingAttempts}
    local wrote,result=pcall(self.storage.Write,self.storage,
        self.key..":rejected:"..tostring(current.transaction.preparedGeneration),fact)
    if not wrote or result~=true then return false,"Rejected cleanup receipt write failed" end
    return persist(self, rejectedOrigin(current.transaction)) -- Retain charged attempt and intermediate item custody.
end

function Methods:RuntimeRejectedReceipt(actionKey,preparedGeneration)
    if self.closed or not text(actionKey,240) or not integer(preparedGeneration,1,MAX) then return nil end
    local ok,fact=pcall(self.storage.Read,self.storage,self.key..":rejected:"..tostring(preparedGeneration))
    if not ok or type(fact)~="table" or uncertainObserved(fact.transaction) or not integer(fact.generation,1,MAX)
        or self.generation~=fact.generation+1 or not valid(fact.transaction,self.scope)
        or fact.transaction.actionKey~=actionKey or fact.transaction.preparedGeneration~=preparedGeneration
        or not equal(self.transaction,rejectedOrigin(fact.transaction))
        or fact.listingAttempts~=self.listingAttempts or fact.withdrawAttempts~=self.withdrawAttempts
        or fact.buyAttempts~=self.buyAttempts or fact.buySpent~=self.buySpent
        or fact.flipListingAttempts~=self.flipListingAttempts then return nil end
    local read,current=pcall(self.storage.Read,self.storage,self.key)
    if not read or not equal(current,self.expected) then return nil end
    return copy(fact)
end

local function prepareIntermediate(self, kind, proposal, before, runtime)
    if self.transaction then return false, "Unresolved Market transaction exists" end
    local evidence = kind == "withdraw" and self.withdrawEvidence or self.buyEvidence
    if type(evidence) ~= "table" or type(proposal) ~= "table"
        or (not runtime and proposal.preflightOnly ~= true)
        or proposal.feature ~= (kind == "withdraw" and "marketSell" or "marketFlip")
        or proposal.account ~= self.scope.account
        or proposal.place ~= self.scope.place
        or proposal.release ~= self.scope.release then
        return false, "Current Market intermediate evidence required"
    end
    local input=proposal
    if runtime then input={} for field,value in pairs(proposal) do input[field]=value end input.preflightOnly=true end
    local ok, baseline = pcall(evidence.capture, input, before)
    if not ok or type(baseline) ~= "table" then
        return false, "Current Market intermediate custody required"
    end
    local intent = proposal.intent
    local record = { kind = kind, stage = "prepared",
        session = baseline.session, account = baseline.account,
        place = baseline.place, release = baseline.release,
        revision = baseline.revision, serverNow = baseline.serverNow,
        expectedAsk = intent.expectedAsk,
        plannedQuantity = kind == "withdraw" and intent.plannedListingQuantity or 1,
        listAttempts = 0, baseline = baseline }
    if runtime then
        record.actionKey,record.sourceKey=proposal.actionKey,proposal.intent.sourceKey
        record.preparedGeneration=self.generation+1
    end
    return persist(self, record)
end

function Methods:PrepareWithdraw(proposal, before)
    return prepareIntermediate(self, "withdraw", proposal, before)
end

function Methods:WithdrawAttempts()
    if self.closed or not integer(self.withdrawAttempts,0,20) then return nil,"Withdrawal allowance unavailable" end
    return self.withdrawAttempts,nil
end
function Methods:PrepareRuntimeWithdraw(proposal,before,maximum)
    local intent=type(proposal)=="table" and proposal.intent
    if not integer(maximum,1,20) or not integer(self.withdrawAttempts,0,20) or self.withdrawAttempts>=maximum
        or not intent or not text(proposal.actionKey,240) or type(intent.sourceKey)~="string" or #intent.sourceKey~=64
        or not intent.sourceKey:match("^[%x]+$") or type(proposal.resources)~="table" or next(proposal.resources)~=nil then
        return false,"Current bounded withdrawal ownership required"
    end
    return prepareIntermediate(self,"withdraw",proposal,before,true)
end
function Methods:AuthorizeRuntimeWithdraw(actionKey,generation,maximum,sourceKey)
    local record=self.transaction
    if self.closed or not record or record.kind~="withdraw" or record.stage~="prepared"
        or record.actionKey~=actionKey or record.sourceKey~=sourceKey or record.preparedGeneration~=generation
        or self.generation~=generation or not integer(maximum,1,20) then return false,"Withdrawal authorization changed" end
    return self:MarkSending(maximum)
end

function Methods:PrepareBuy(proposal, before)
    return prepareIntermediate(self, "buy", proposal, before)
end

function Methods:BuyUsage()
    if self.closed or not integer(self.buyAttempts,0,20) or not integer(self.buySpent,0,1000000000)
        or self.buySpent<self.buyAttempts or self.buyAttempts==0 and self.buySpent~=0 then return nil end
    return {attempted=self.buyAttempts,spent=self.buySpent}
end
function Methods:PrepareRuntimeBuy(proposal,before)
    local i=type(proposal)=="table" and proposal.intent
    local usage=self:BuyUsage()
    if not usage or type(i)~="table" or not text(proposal.actionKey,240)
        or type(i.sourceKey)~="string" or #i.sourceKey~=64 or not i.sourceKey:match("^[%x]+$")
        or i.ownerGeneration~=self.generation+1 or i.attemptedBefore~=usage.attempted or i.spentBefore~=usage.spent
        or not integer(i.maxAttempts,1,20) or usage.attempted>=i.maxAttempts
        or not integer(i.sessionBudget,1,1000000000) or not integer(i.quotedPrice,1,9999999)
        or usage.spent+i.quotedPrice>i.sessionBudget or type(proposal.resources)~="table"
        or proposal.resources.gold_bar~=i.quotedPrice then return false,"Current independent buy allowance required" end
    for resource in pairs(proposal.resources) do if resource~="gold_bar" then return false,"Unexpected buy exposure" end end
    return prepareIntermediate(self,"buy",proposal,before,true)
end
function Methods:AuthorizeRuntimeBuy(proposal)
    local r=self.transaction
    local i=type(proposal)=="table" and proposal.intent
    if self.closed or not r or r.kind~="buy" or r.stage~="prepared" or type(i)~="table"
        or r.actionKey~=proposal.actionKey or r.preparedGeneration~=i.ownerGeneration or self.generation~=i.ownerGeneration
        or r.sourceKey~=i.sourceKey or r.baseline.itemId~=i.itemId or r.baseline.listingId~=i.listingId
        or r.baseline.price~=i.quotedPrice or r.expectedAsk~=i.expectedAsk
        or i.attemptedBefore~=self.buyAttempts or i.spentBefore~=self.buySpent
        or not integer(i.maxAttempts,1,20) or self.buyAttempts>=i.maxAttempts
        or not integer(i.sessionBudget,1,1000000000) or self.buySpent+i.quotedPrice>i.sessionBudget
        or type(proposal.resources)~="table" or proposal.resources.gold_bar~=i.quotedPrice then
        return false,"Buy authorization or allowance changed" end
    for resource in pairs(proposal.resources) do if resource~="gold_bar" then return false,"Unexpected buy exposure" end end
    local nextRecord=copy(r);nextRecord.stage="sent"
    return persist(self,nextRecord,nil,nil,self.buyAttempts+1,self.buySpent+i.quotedPrice)
end

local function currentHeader(raw, scope)
    return header(type(raw) == "table" and {
        session = raw.session, account = raw.account, place = raw.place,
        release = raw.release, revision = raw.revision,
        serverNow = type(raw.native) == "table" and raw.native.serverNow,
    } or nil, scope)
        and raw.native.fullSync == true
end

local function observeIntermediate(self, record, raw)
    local evidence = record.kind == "withdraw" and self.withdrawEvidence or self.buyEvidence
    if type(evidence) ~= "table" then return false end
    local ok, observed = pcall(evidence.observe, record.baseline, raw)
    return ok and observed == true
end

function Methods:ListingContext(raw, now, preparedActionKey)
    self.listingProof = nil
    local record = self.transaction
    if uncertainObserved(record) then return nil, "Observed Market callback remains uncertain" end
    if record and record.kind=="list" and record.stage=="prepared" and record.actionKey==preparedActionKey then record=record.origin end
    if not record or record.stage ~= "observed"
        or (record.kind ~= "withdraw" and record.kind ~= "buy")
        or not currentHeader(raw, self.scope) or not finite(now)
        or not finite(raw.capturedAt) or raw.capturedAt > now + 1
        or now - raw.capturedAt > 15
        or raw.native.serverNow < record.confirmedServerNow
        or raw.native.serverNow - record.confirmedServerNow
            + math.max(0, now - raw.capturedAt) > 3600
        or (raw.session == record.confirmedSession
            and raw.revision < record.confirmedRevision)
        or (raw.session ~= record.confirmedSession
            and raw.native.serverNow <= record.confirmedServerNow)
        or not observeIntermediate(self, record, raw) then
        return nil, "Fresh exact intermediate Market custody required"
    end
    local b = record.baseline
    -- Local time can reset on restart. Retain native elapsed age, even when
    -- the rebased local confirmation precedes the new local clock epoch.
    local view = { session = raw.session, account = raw.account,
        place = raw.place, release = raw.release,
        itemId = b.itemId, listAttempts = record.listAttempts,
        expectedAsk = record.expectedAsk,
        confirmedRevision = raw.revision,
        confirmedAt = now - (raw.native.serverNow - record.confirmedServerNow)
            - math.max(0, now - raw.capturedAt) }
    if record.kind == "withdraw" then
        view.stage = "withdrawn"
        view.withdrawnQuantity = b.quantity
        view.plannedQuantity = record.plannedQuantity
        view.beforeLoose, view.beforeBound = b.loose, b.bound
        view.beforeCollected, view.checkpointFloor = b.collected, b.floor
    else
        view.stage = "bought"
        view.sourceListingId, view.buyPrice = b.listingId, b.price
        view.beforeLoose, view.boundBefore = b.item, b.boundItem
    end
    self.listingProof = { session = raw.session, revision = raw.revision,
        capturedAt = raw.capturedAt, serverNow = raw.native.serverNow,
        now = now }
    return view, nil
end

local function prepareFollowupList(self,proposal,before,now,runtime)
    local record, proof = self.transaction, self.listingProof
    local intent = type(proposal) == "table" and proposal.intent
    if not record or uncertainObserved(record) or not proof or not finite(now) or now < proof.now
        or record.stage ~= "observed"
        or (record.kind ~= "withdraw" and record.kind ~= "buy")
        or type(intent) ~= "table" or intent.kind ~= "marketList"
        or (not runtime and proposal.preflightOnly ~= true)
        or proposal.feature ~= (record.kind == "withdraw" and "marketSell" or "marketFlip")
        or type(before) ~= "table"
        or proposal.session ~= proof.session or before.session ~= proof.session
        or proposal.revision ~= proof.revision or before.revision ~= proof.revision
        or (not runtime and proposal.capturedAt ~= proof.capturedAt) or before.capturedAt ~= proof.capturedAt
        or type(before.native) ~= "table" or before.native.serverNow ~= proof.serverNow
        or proposal.account ~= self.scope.account
        or proposal.place ~= self.scope.place or proposal.release ~= self.scope.release
        or intent.itemId ~= record.baseline.itemId
        or intent.quantity ~= record.plannedQuantity
        or intent.ask ~= record.expectedAsk
        or type(self.listEvidence) ~= "table" then
        return false, "Matching freshly assessed Market listing required"
    end
    if record.kind == "withdraw" then
        if intent.collectionWithdrawn ~= record.baseline.quantity then
            return false, "Original Collection withdrawal required"
        end
    elseif intent.sourceListingId ~= record.baseline.listingId
        or intent.buyPrice ~= record.baseline.price then
        return false, "Original Market purchase required"
    end
    if not self:ListingContext(before, now) then
        return false, "Intermediate Market custody changed"
    end
    local input=proposal
    if runtime then input={} for k,v in pairs(proposal) do input[k]=v end input.preflightOnly=true end
    local ok, baseline = pcall(self.listEvidence.capture, input, before)
    if not ok or type(baseline) ~= "table" then
        return false, "Current follow-up listing custody required"
    end
    baseline.kind, baseline.stage = "list", "prepared"
    baseline.origin, baseline.listAttempts = copy(record), record.listAttempts + 1
    if runtime then
        baseline.actionKey,baseline.sourceKey=proposal.actionKey,intent.sourceKey
        baseline.preparedGeneration=self.generation+1
    end
    return persist(self, baseline)
end

function Methods:PrepareFollowupList(proposal,before,now)
    return prepareFollowupList(self,proposal,before,now,false)
end
function Methods:PrepareRuntimeFollowupList(proposal,before,now,maximum)
    if not integer(maximum,1,20) or not integer(self.listingAttempts,0,20)
        or (self.transaction and self.transaction.kind=="buy" and (not integer(self.flipListingAttempts,0,399) or self.transaction.listAttempts>=maximum)
            or self.transaction and self.transaction.kind~="buy" and self.listingAttempts>=maximum)
        or not proposal.intent or proposal.intent.ownerGeneration~=self.generation+1
        or proposal.intent.sourceKey~=self.transaction.sourceKey then return false,"Bounded continuation changed" end
    return prepareFollowupList(self,proposal,before,now,true)
end

function Methods:ListingAttempts(feature)
    if feature=="marketFlip" then
        if self.closed or not integer(self.flipListingAttempts,0,400) then return nil,"Flip listing usage unavailable" end
        return self.flipListingAttempts,nil
    end
    if self.closed or not integer(self.listingAttempts, 0, 20) then
        return nil, "Listing allowance requires current durable ownership"
    end
    return self.listingAttempts, nil
end

function Methods:MarkSending(maxListingAttempts)
    if not self.transaction or uncertainObserved(self.transaction)
        or self.transaction.stage ~= "prepared" then
        return false, "No prepared Market transaction"
    end
    local attempted = self.listingAttempts
    local flipped=self.flipListingAttempts
    if flipList(self.transaction) then
        local maximum=maxListingAttempts or 20
        if not integer(flipped,0,399) or not integer(maximum,1,20) or self.transaction.origin.listAttempts>=maximum then return false,"Purchased-copy listing allowance exhausted" end
        flipped=flipped+1
    elseif self.transaction.kind == "list" then
        local maximum = maxListingAttempts == nil and 20 or maxListingAttempts
        if not integer(attempted, 0, 20) or not integer(maximum, 1, 20)
            or attempted >= maximum then return false, "Listing attempt allowance exhausted or unavailable" end
        attempted = attempted + 1
    end
    local withdrawn=self.withdrawAttempts
    if self.transaction.kind=="withdraw" and self.transaction.actionKey~=nil then
        if not integer(withdrawn,0,20) or not integer(maxListingAttempts,1,20) or withdrawn>=maxListingAttempts then
            return false,"Withdrawal attempt allowance exhausted"
        end
        withdrawn=withdrawn+1
    end
    local nextRecord = copy(self.transaction)
    nextRecord.stage = "sent"
    return persist(self, nextRecord, attempted,withdrawn,nil,nil,flipped)
end

function Methods:Reconcile(raw)
    local record = self.transaction
    if not record then return "idle", nil end
    if uncertainObserved(record) then return "uncertain", "Observed Market callback remains uncertain; custody retained" end
    if record.stage == "prepared" then
        return "prepared", "Send was not authorized by the durable record"
    end
    if record.stage == "observed" then return "observed", nil end
    if record.actionKey ~= nil and (type(record.reply) ~= "table"
        or record.reply.ok ~= true or record.reply.pending == true
        or record.reply.code == "pending" or record.reply.code == "busy"
        or record.reply.code == "rate_limited" or record.reply.code == "presence") then
        return "uncertain", "Matching definitive listing reply required"
    end
    if record.kind == "withdraw" or record.kind == "buy" then
        if record.kind=="withdraw" and record.actionKey~=nil and record.reply.moved~=record.baseline.quantity then
            return "uncertain","Exact native withdrawal result required"
        end
        if not currentHeader(raw, self.scope) then
            return "waiting", "Current full Market custody Sync required"
        end
        if raw.native.serverNow < record.serverNow
            or (raw.session == record.session and raw.revision <= record.revision)
            or (raw.session ~= record.session and raw.native.serverNow <= record.serverNow) then
            return "waiting", "Newer Market custody Sync required"
        end
        if not observeIntermediate(self, record, raw) then
            return "uncertain", "Market custody outcome ambiguous; do not retry"
        end
        local nextRecord = copy(record)
        nextRecord.stage = "observed"
        nextRecord.confirmedServerNow = raw.native.serverNow
        nextRecord.confirmedSession, nextRecord.confirmedRevision = raw.session, raw.revision
        local saved, reason = persist(self, nextRecord)
        return saved and "observed" or "uncertain", reason
    end
    if record.kind == "list" then
        if type(raw) ~= "table"
            or raw.account ~= self.scope.account
            or raw.place ~= self.scope.place
            or raw.release ~= self.scope.release
            or type(raw.session) ~= "string"
            or not integer(raw.revision, 0, 9007199254740991)
            or type(raw.native) ~= "table"
            or raw.native.fullSync ~= true then
            return "waiting", "Current full owned-listing Sync required"
        end
        local sameSession = raw.session == record.session
        if sameSession and raw.revision <= record.revision
            or not sameSession
                and (not finite(raw.native.serverNow)
                    or raw.native.serverNow <= record.serverNow) then
            return "waiting", "Newer owned-listing Sync required"
        end
        if type(self.listEvidence) ~= "table" then
            return "uncertain", "Listing evidence unavailable; do not retry"
        end
        local ok, observed = pcall(self.listEvidence.observe,
            record, raw)
        if ok and observed == true then
            local nextRecord = copy(record)
            nextRecord.stage = "observed"
            local saved, reason = persist(self, nextRecord)
            return saved and "observed" or "uncertain", reason
        end
        return "uncertain", "Listing outcome ambiguous; do not retry"
    end
    local current = state(raw, self.scope)
    if not current then return "waiting", "Current full Market Sync required" end
    local sameSession = current.session == record.session
    if sameSession and current.revision <= record.revision
        or not sameSession
            and current.serverNow <= record.serverNow then
        return "waiting", "Newer Market Sync required"
    end
    local expectedUntil = math.floor(math.max(record.serverNow,
        record.shopUntil)) + record.durationSeconds
    local latestUntil = math.ceil(math.max(current.serverNow, record.shopUntil)) + record.durationSeconds
    if current.serverNow >= record.serverNow
        and current.shopUntil >= expectedUntil
        and current.shopUntil <= latestUntil
        and current.shopUntil > current.serverNow
        and current.loose == record.loose - record.cost
        and current.bound == record.bound then
        local nextRecord = copy(record)
        nextRecord.stage = "observed"
        local saved, reason = persist(self, nextRecord)
        return saved and "observed" or "uncertain", reason
    end
    return "uncertain", "Rental outcome ambiguous; do not retry"
end

-- Explicit local release of an exactly observed withdrawal; inventory and usage stay unchanged.
function Methods:ObservedIntermediateReview(raw,now)
    local record=self.transaction
    if self.closed or writers[self.key] or not record or uncertainObserved(record) or (record.kind~="withdraw" and record.kind~="buy")
        or record.stage~="observed" or not text(record.actionKey,240) then return nil,"No observed withdrawal" end
    if not currentHeader(raw,self.scope) or not finite(now) or not finite(raw.capturedAt)
        or raw.capturedAt>now or now-raw.capturedAt>2
        or raw.native.serverNow<record.confirmedServerNow
        or not observeIntermediate(self,record,raw) then return nil,"Exact current withdrawn-item custody required" end
    return {generation=self.generation,transaction=copy(record),listingAttempts=self.listingAttempts,
        withdrawAttempts=self.withdrawAttempts,buyAttempts=self.buyAttempts,buySpent=self.buySpent},nil
end
function Methods:ReleaseObservedIntermediate(review,raw,now)
    local current,reason=self:ObservedIntermediateReview(raw,now)
    if not current or not equal(current,review) then return false,reason or "Observed withdrawal changed" end
    return persist(self,nil) -- No refund, sale, redeposit or allowance reset.
end

Methods.ObservedWithdrawalReview=Methods.ObservedIntermediateReview
Methods.ReleaseObservedWithdrawal=Methods.ReleaseObservedIntermediate

function Methods:ClearObserved()
    if not self.transaction or uncertainObserved(self.transaction)
        or self.transaction.stage ~= "observed"
        or self.transaction.kind == "withdraw"
        or self.transaction.kind == "buy" then
        return false, "No final observed Market transaction"
    end
    return persist(self, nil)
end

return MarketTransactions
