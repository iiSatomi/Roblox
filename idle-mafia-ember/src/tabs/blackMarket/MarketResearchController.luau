-- Read-only research state. All network admission belongs to ReadCoordinator.
local MarketResearchController = {}
local headers = {"session", "account", "place", "release", "revision", "capturedAt"}
function MarketResearchController.new(deps)
    assert(type(deps.clock) == "table" and type(deps.identity) == "table"
        and type(deps.gameData) == "table" and type(deps.gameData.ITEMS_BY_ID) == "table",
        "Missing Market research sources")
    local researchFeature=deps.researchFeature or "marketWatch"
    assert(researchFeature=="marketWatch" or researchFeature=="marketFlip","Invalid Market research feature")
    local identity, items = {}, {}
    for _, key in ipairs({"session", "account", "place", "release"}) do
        assert(type(deps.identity[key]) == "string" and #deps.identity[key] > 0, "Invalid Market research identity")
        identity[key] = deps.identity[key]
    end
    assert(identity.release == deps.release, "Market research release mismatch")
    for id, row in pairs(deps.gameData.ITEMS_BY_ID) do
        if type(id) == "string" and type(row) == "table" then
            items[id] = {id = id, kind = row.kind, rarity = row.rarity, tradable = row.tradable == true}
        end
    end
    local saleOwner, collectionCatalog
    if type(deps.NativeCollectionCatalog)=="table" and type(deps.config.COLLECTION)=="table" then
        local ok,value=pcall(deps.NativeCollectionCatalog.new,deps.gameData,deps.config,deps.fingerprint,deps.release)
        if ok then collectionCatalog=value end
    end
    local clock = deps.clock
    local catalog = deps.NativeMarketCatalog.new(deps.config, deps.fingerprint, deps.release)
    local browse = deps.MarketBrowse.new(catalog.maxPages, clock)
    local pages = deps.MarketBrowsePages.new(catalog.maxPages, 500, deps.MarketBrowse.matchesItemScope)
    local rap, prices = deps.MarketRap.new(clock), deps.MarketPrices.new(clock)
    local function saleReaders()
        return deps.MarketBrowse.new(catalog.maxPages, clock), deps.MarketBrowsePages.new(catalog.maxPages, 500, deps.MarketBrowse.matchesItemScope),
            deps.MarketRap.new(clock), deps.MarketPrices.new(clock)
    end
    local saleBrowse, salePages, saleRap, salePrices = saleReaders()
    local state = {closed = false, options = nil, browse = nil, nextPage = nil,
        nextBrowseAt = 0, ownedItems = {}, saleOptions = nil,
        saleGeneration = 0, saleRejected = {}, saleRequest = nil, saleCandidate = nil,
        saleBrowse = nil, saleNextPage = nil, saleNextAt = 0}
    local owner = {}
    function owner:AttachSaleOwner(value)
        assert(saleOwner==nil or saleOwner==value,"Sale owner already attached")
        saleOwner=value
    end
    local function preferences(settings)
        local selected = type(settings) == "table" and settings[researchFeature]
        if type(selected) ~= "table" or selected.enabled ~= true then return nil, "Market watch disabled" end
        local result = {}
        for key, value in pairs(selected.custom or selected) do result[key] = value end
        result.enabled = true
        if researchFeature=="marketFlip" then
            local readOptions={enabled=true,minAgeHours=1,demandMultiplier=1,maxReviews=1}
            for _,key in ipairs({"scope","selectedItemId","excludedItems","excludedKinds","excludedRarities",
                "minSales","minUnits","minMargin","minMarginPct","undercutGold","floorPct","requireCoverage"}) do
                readOptions[key]=result[key]
            end
            result=readOptions
        end
        return deps.MarketSettings.project("marketWatch", result)
    end
    local function salePreferences(settings)
        local selected = type(settings) == "table" and settings[researchFeature=="marketFlip" and "marketFlip" or "marketSell"]
        if type(selected) ~= "table" or selected.enabled ~= true then return nil end
        local result = {}
        for key, value in pairs(selected.custom or selected) do result[key] = value end
        result.enabled = true
        if researchFeature=="marketFlip" then result.keepLoose=0;result.fromCollection=false end
        if type(result.keepLoose) ~= "number" or result.keepLoose ~= result.keepLoose
            or result.keepLoose % 1 ~= 0 or result.keepLoose < 0
            or result.keepLoose > 999 then return nil end
        local projected = deps.MarketSettings.projectSelection(result)
        if not projected then return nil end
        return {selection = projected.selection, keepLoose = result.keepLoose, fromCollection = result.fromCollection == true,
            key = table.concat({result.scope, result.selectedItemId,
                result.excludedItems, result.excludedKinds,
                result.excludedRarities, tostring(result.keepLoose), tostring(result.fromCollection == true)}, "\31")}
    end
    local function resetSale(options)
        state.saleGeneration = state.saleGeneration + 1
        state.saleOptions, state.saleRequest, state.saleCandidate = options, nil, nil
        state.saleRejected = {}
        state.saleBrowse, state.saleNextPage, state.saleNextAt = nil, nil, 0
        saleBrowse:Close(); salePages:Close(); saleRap:Close(); salePrices:Close()
        saleBrowse, salePages, saleRap, salePrices = saleReaders()
    end
    local function scoped(raw, context)
        if type(raw) ~= "table" or type(raw.native) ~= "table" or raw.native.fullSync ~= true then return false end
        for key, value in pairs(identity) do if raw[key] ~= value then return false end end
        if context then for _, key in ipairs(headers) do if raw[key] ~= context[key] then return false end end end
        return type(raw.capturedAt) == "number" and raw.capturedAt <= clock:Now() and clock:Now() - raw.capturedAt <= 2
    end
    local function saleCandidate(raw)
        local options = state.saleOptions
        local native = type(raw) == "table" and raw.native
        local inventory = type(native) == "table" and native.inventory
        local bound = type(native) == "table" and native.inventoryBound
        if not options or type(inventory) ~= "table"
            or type(bound) ~= "table" or not scoped(raw) then return nil end
        local active=saleOwner and saleOwner:Active()
        if researchFeature=="marketFlip" then
            if active and active.sourceKey==deps.fingerprint then
                if active.kind=="buy" and active.stage=="observed" then return active.baseline.itemId end
                if active.kind=="list" and active.stage=="prepared" and active.origin and active.origin.kind=="buy" then return active.itemId end
            end
            return nil
        end
        if active and active.kind=="withdraw" and active.stage=="observed" and active.sourceKey==deps.fingerprint then return active.baseline.itemId end
        local ids, candidates = {}, {}
        for id in pairs(inventory) do candidates[id]=true end
        if options.fromCollection and type(native.collection)=="table" then
            for id in pairs(native.collection) do candidates[id]=true end
        end
        for id in pairs(candidates) do
            local amount=inventory[id] or 0
            local collected=type(native.collection)=="table" and native.collection[id] or 0
            local item = items[id]
            local boundAmount = bound[id] or 0
            if item and item.tradable and type(amount) == "number"
                and amount == amount and amount % 1 == 0 and amount >= 0
                and amount <= 1000000000 and type(boundAmount) == "number"
                and boundAmount == boundAmount and boundAmount % 1 == 0
                and boundAmount >= 0 and boundAmount <= 1000000000
                and (amount > options.keepLoose or options.fromCollection and type(collected)=="number" and collected>0)
                and (not state.saleRejected[id] or clock:Now() >= state.saleRejected[id])
                and deps.MarketSettings.allows({selection = options.selection}, item)
                and (options.selection.scope ~= "Selected item"
                    or id == options.selection.selectedItemId) then
                ids[#ids + 1] = id
            end
        end
        table.sort(ids)
        return ids[1]
    end
    local function rejectSaleItem(id)
        if not state.saleOptions or state.saleOptions.selection.scope ~= "All eligible items" then return end
        local count = 0
        for key, untilAt in pairs(state.saleRejected) do
            if clock:Now() >= untilAt then state.saleRejected[key] = nil
            else count = count + 1 end
        end
        if count < 100 then state.saleRejected[id] = clock:Now() + 15 end
    end
    local function selectedIds()
        local result, seen = {}, {}
        if not state.options or not state.browse or clock:Now() - state.browse.capturedAt > 120 then return result end
        for _, row in ipairs(state.browse.rows) do
            local item = items[row.item]
            if item and deps.MarketSettings.allows(state.options, item) and not seen[item.id] then
                seen[item.id] = true
                result[#result + 1] = item.id
                if #result >= 100 then break end
            end
        end
        for id in pairs(state.ownedItems) do
            local item = items[id]
            if #result < 100 and not seen[id] and item and deps.MarketSettings.allows(state.options, item) then
                seen[id], result[#result + 1] = true, id
            end
        end
        table.sort(result)
        return result
    end
    local function missingRap()
        local ids = {}
        for _, id in ipairs(selectedIds()) do
            if not rap:Get(id) then ids[#ids + 1] = id end
            if #ids == 20 then break end
        end
        return ids
    end
    local function missingPrice()
        for _, id in ipairs(selectedIds()) do if not prices:Get(id) then return id end end
        return nil
    end
    local function researchScope(options)
        local selection = options and options.selection
        if selection and selection.scope == "Selected item" then return "item", selection.selectedItemId end
        return "all", nil
    end
    local function currentResearchScope(value)
        local kind, arg = researchScope(state.options)
        return type(value) == "table" and value.kind == kind and value.arg == arg
    end
    function owner:Sources()
        local sources = {}
        for _, kindName in ipairs({"browse", "rap", "prices"}) do
            local kind = kindName
            sources[#sources + 1] = {id = (researchFeature=="marketFlip" and "marketFlip" or "market") .. kind:sub(1, 1):upper() .. kind:sub(2), interval = 1,
                enabled = function(settings)
                    if state.closed then state.options, state.preferenceReason = nil, "Market reader closed"
                    else state.options, state.preferenceReason = preferences(settings) end
                    if not state.options then
                        state.nextPage, state.browse, state.nextBrowseAt, state.ownedItems = nil, nil, 0, {}
                        return false
                    end
                    if state.browse and not currentResearchScope(state.browse)
                        or state.nextPage and not currentResearchScope(state.nextPage) then
                        state.nextPage, state.browse, state.nextBrowseAt = nil, nil, 0
                    end
                    if kind == "browse" then return state.nextPage ~= nil or clock:Now() >= state.nextBrowseAt end
                    if kind == "rap" then return #missingRap() > 0 end
                    return missingPrice() ~= nil
                end,
                prepare = function(raw)
                    if state.closed or not state.options or not scoped(raw) then return nil, "Current Market research Sync required" end
                    if kind == "browse" then
                        if not state.nextPage then
                            local scope, arg = researchScope(state.options)
                            state.nextPage = pages:Begin(scope, arg)
                        end
                        return browse:Prepare(state.nextPage)
                    elseif kind == "rap" then return rap:Prepare(missingRap()) end
                    return prices:Prepare(missingPrice())
                end,
                accept = function(raw, request, reply)
                    if state.closed or not state.options or not scoped(raw) then return nil end
                    if kind == "browse" and not currentResearchScope(request) then return nil end
                    local query = kind == "browse" and browse or kind == "rap" and rap or prices
                    return query:Accept(request, reply)
                end,
                commit = function(value)
                    if state.closed or not state.options then return false end
                    if kind == "browse" then
                        local nextPage, completed, reason = pages:Accept(value)
                        state.nextPage = nextPage
                        if reason then
                            state.browse, state.nextBrowseAt = nil, clock:Now() + 5
                            return false
                        end
                        if completed and currentResearchScope(completed) then
                            state.browse, state.nextBrowseAt = completed, clock:Now() + 10
                        end
                    end
                    return true
                end,
            }
        end
        for _, kindName in ipairs({"browse", "rap", "prices"}) do
            local kind = kindName
            sources[#sources + 1] = {id = (researchFeature=="marketFlip" and "marketFlipList" or "marketSell") .. kind:sub(1, 1):upper() .. kind:sub(2), interval = 1,
                enabled = function(settings)
                    if state.closed then return false end
                    local selected = salePreferences(settings)
                    if not selected then
                        if state.saleOptions or state.saleRequest or state.saleBrowse then resetSale(nil) end
                        return false
                    end
                    if not state.saleOptions or selected.key ~= state.saleOptions.key then resetSale(selected) end
                    if kind == "browse" then return not state.saleBrowse
                        or clock:Now() - state.saleBrowse.capturedAt >= 15 end
                    if kind == "rap" then return true end
                    return true
                end,
                prepare = function(raw)
                    if state.closed or not state.saleOptions or not scoped(raw) then return nil, "Current Market sale Sync required" end
                    local id = saleCandidate(raw)
                    if not id then state.saleCandidate = nil; return nil, "No eligible loose Market item" end
                    if state.saleCandidate ~= id then
                        state.saleGeneration = state.saleGeneration + 1
                        state.saleCandidate, state.saleBrowse, state.saleNextPage = id, nil, nil
                    end
                    local query, request
                    if kind == "browse" then
                        if state.saleBrowse and clock:Now() - state.saleBrowse.capturedAt < 15 then return nil, "Item browse cached" end
                        if not state.saleNextPage then state.saleNextPage = salePages:Begin("item", id) end
                        request = saleBrowse:Prepare(state.saleNextPage)
                        query = saleBrowse
                    elseif kind == "rap" then
                        if saleRap:Get(id) then return nil, "Item RAP cached" end
                        request = saleRap:Prepare({id})
                        query = saleRap
                    else
                        if salePrices:Get(id) then return nil, "Item prices cached" end
                        request = salePrices:Prepare(id)
                        query = salePrices
                    end
                    if not request then return nil end
                    state.saleRequest = {request = request, query = query,
                        generation = state.saleGeneration, kind = kind, itemId = id}
                    return request
                end,
                accept = function(raw, request, reply)
                    local pending = state.saleRequest
                    if state.closed or not state.saleOptions or not pending
                        or pending.request ~= request
                        or pending.generation ~= state.saleGeneration
                        or pending.itemId ~= saleCandidate(raw)
                        or not scoped(raw) then return nil end
                    return pending.query:Accept(request, reply)
                end,
                commit = function(value)
                    local pending = state.saleRequest
                    if state.closed or not pending or pending.generation ~= state.saleGeneration then return false end
                    state.saleRequest = nil
                    if kind == "browse" then
                        local nextPage, completed, reason = salePages:Accept(value)
                        state.saleNextPage = nextPage
                        if reason then state.saleBrowse = nil; return false end
                        if completed then state.saleBrowse, state.saleNextPage = completed, nil end
                    end
                    return true
                end,
            }
        end
        return sources
    end
    function owner:SaleView(raw, context)
        if state.closed then return nil, "Market reader closed" end
        if not state.saleOptions then return nil, "Market sale research disabled" end
        if not scoped(raw, context) then return nil, "Market sale snapshot changed or stale" end
        local id = saleCandidate(raw)
        if not id then return nil, "No eligible loose Market item" end
        if id ~= state.saleCandidate then return nil, "Market sale selection changed" end
        local browseResult, rapResult, priceResult = state.saleBrowse,
            saleRap:Get(id), salePrices:Get(id)
        if type(browseResult) ~= "table" or browseResult.kind ~= "item"
            or browseResult.arg ~= id or browseResult.more ~= false
            or browseResult.stale == true or browseResult.small == true
            or clock:Now() - browseResult.capturedAt > 15
            or not rapResult or not priceResult then
            return nil, "Waiting for complete current item browse, RAP and history"
        end
        for _, row in ipairs(browseResult.rows) do
            if row.item:find("@", 1, true) then return nil, "Variant-inclusive Market browse cannot authorize a sale" end
        end
        return {readOnly = true, raw = raw, context = context, itemId = id, browse = browseResult,
            rap = rapResult, history = priceResult, session = raw.session,
            account = raw.account, place = raw.place, release = raw.release,
            revision = raw.revision, capturedAt = raw.capturedAt}, nil
    end
    function owner:SalePreview(view, settings)
        if state.closed or type(view) ~= "table" or type(settings) ~= "table"
            or settings.enabled ~= true then return nil, "Market sale preview disabled" end
        local raw, context = view.raw, view.context
        if not scoped(raw, context) or saleCandidate(raw) ~= view.itemId then
            return nil, "Market sale preview changed or stale"
        end
        -- Re-read owned caches; caller-supplied research cannot authorize pricing.
        local current, reason = self:SaleView(raw, context)
        if not current then return nil, reason end
        local options = settings.custom or settings
        local projected
        projected, reason = deps.MarketSettings.projectSalePreview(options)
        if not projected then return nil, reason end
        local item = items[current.itemId]
        if not deps.MarketSettings.allows(projected, item) then return nil, "Item excluded from sale preview" end
        if type(deps.MarketSaleCustody) ~= "table" or type(deps.MarketSaleQuote) ~= "table" then
            return nil, "Market sale preview modules unavailable"
        end
        local custody
        local tiers
        local active=saleOwner and saleOwner:Active()
        if active and active.kind=="withdraw" and active.stage=="observed" then
            projected.custody.fromCollection=false
            local original=type(context)=="table" and context.collectionProtection
            local held=original and original.reserved and original.reserved[current.itemId]
            if type(held)~="number" or held<active.plannedQuantity then return nil,"Owned continuation reservation unavailable" end
            local proof, reserved, adjusted={},{},{}
            for key,value in pairs(original) do proof[key]=value end
            for key,value in pairs(original.reserved) do reserved[key]=value end
            reserved[current.itemId]=held-active.plannedQuantity;proof.reserved=reserved
            for key,value in pairs(context) do adjusted[key]=value end
            adjusted.collectionProtection=proof;context=adjusted
        elseif projected.custody.fromCollection then
            if not collectionCatalog then return nil,"Native Collection tiers unavailable" end
            local enriched=collectionCatalog:Enrich(raw)
            if not enriched then return nil,"Current Collection tiers unavailable" end
            tiers=enriched.collectionCatalog.tiers
        end
        custody, reason = deps.MarketSaleCustody.assess(raw, context,
            current.itemId, item, projected.custody, tiers)
        if not custody then
            if reason == "No unbound Market sale surplus" then rejectSaleItem(current.itemId) end
            return nil, reason
        end
        local listings
        listings, reason = deps.MarketListingsState.read(raw, context)
        if not listings then return nil, reason end
        local terms
        terms, reason = catalog:SaleTerms(raw, item.rarity)
        if not terms then return nil, reason end
        local quote
        quote, reason = deps.MarketSaleQuote.assess(custody, current.rap,
            current.history, current.browse, listings, terms, projected.quote, clock:Now())
        if not quote then
            local unsuitable = reason == "Market item has insufficient recent demand"
                or reason == "Conservative Market ask unavailable"
                or reason == "Market net Gold below minimum"
                or reason == "Market demand threshold not met"
                or reason == "Visible supply exceeds Market demand"
                or reason == "Market demand coverage below minimum"
            if unsuitable then rejectSaleItem(current.itemId) end
            return nil, reason
        end
        return {readOnly = true, custody = custody, quote = quote, terms = terms}, nil
    end
    -- Construct a bounded intent only; the live descriptor still does not send.
    function owner:PlanSale(view, settings)
        local preview, reason = self:SalePreview(view, settings)
        if not preview then return nil, reason end
        local raw = view.raw
        local proof = raw.marketSellOwnerProof
        if type(proof) ~= "table" then return nil, "Owned listing allowance required" end
        for _, field in ipairs(headers) do
            if proof[field] ~= raw[field] then return nil, "Listing owner snapshot changed" end
        end
        if type(proof.attempted) ~= "number" or proof.attempted % 1 ~= 0
            or proof.attempted < 0 or proof.attempted > 20
            or type(proof.generation) ~= "number" or proof.generation % 1 ~= 0
            or proof.generation < 0 or proof.generation >= 9007199254740991
            or type(proof.transactionOpen) ~= "boolean" then
            return nil, "Listing owner allowance invalid"
        end
        local options = {}
        for key, value in pairs(settings.custom or settings) do options[key] = value end
        options.enabled = settings.enabled
        if options.fromCollection and (type(proof.withdrawAttempts)~="number" or proof.withdrawAttempts%1~=0
            or proof.withdrawAttempts<0 or proof.withdrawAttempts>20) then return nil,"Owned withdrawal allowance required" end
        local projected
        projected, reason = deps.MarketSettings.project("marketSell", options,
            {listingAttempts = proof.attempted, withdrawAttempts = proof.withdrawAttempts or 0, transactionOpen = proof.transactionOpen})
        if not projected then return nil, reason end
        local maximum = math.min(options.maxListings, options.maxListAttempts)
        if proof.attempted >= maximum then return nil, "Listing attempt allowance exhausted" end
        local listings = deps.MarketListingsState.read(raw, view.context)
        local proposal
        local active=saleOwner and saleOwner:Active()
        local withdrawing=false
        if active and active.kind=="withdraw" and active.stage=="observed" and active.sourceKey==deps.fingerprint then
            local tx=saleOwner:ListingContext(raw,clock:Now())
            if not tx then return nil,"Withdrawn sale custody changed" end
            proposal,reason=deps.MarketSellListPreflight.assess(tx,preview.custody,preview.quote,
                listings,preview.terms,projected.followupList,clock:Now())
        elseif preview.custody.withdraw>0 then
            if proof.transactionOpen then return nil,"Unresolved Market transaction exists" end
            -- The native command has no origin argument; do not guess mixed-origin order.
            for _,map in ipairs({raw.native.collection,raw.native.collectionBound}) do
                for id,amount in pairs(map or {}) do
                    if amount~=0 and ((map==raw.native.collectionBound and id==preview.custody.itemId)
                        or id:sub(1,#preview.custody.itemId+1)==preview.custody.itemId.."@") then
                        return nil,"Mixed bound or upgraded Collection withdrawal is manual"
                    end
                end
            end
            proposal,reason=deps.MarketCollectionWithdrawPreflight.assess(preview.custody,preview.quote,
                listings,preview.terms,projected.withdraw,proof.withdrawAttempts,clock:Now())
            withdrawing=true
        else
            proposal,reason=deps.MarketSellDirectPreflight.assess(preview.custody,
                preview.quote,listings,preview.terms,projected.directList,proof.attempted,clock:Now())
        end
        if not proposal then return nil, reason end
        if type(deps.marketPresence) ~= "table" or type(deps.marketPresence.check) ~= "function" then
            return nil, "Native Market preflight unavailable"
        end
        local checked, allowed, gateReason = pcall(deps.marketPresence.check)
        if not checked or allowed ~= true then return nil, checked and gateReason or "Native Market preflight failed" end
        proposal.preflightOnly = nil
        proposal.actionKey = (withdrawing and "market-withdraw:" or "market-list:") .. preview.terms.sourceKey .. ":"
            .. tostring(proof.generation + 1) .. ":" .. preview.custody.itemId
        proposal.resources = withdrawing and {} or {[preview.custody.itemId] = preview.quote.quantity}
        proposal.intent.sourceKey = preview.terms.sourceKey
        proposal.intent.ownerGeneration = proof.generation + 1
        proposal.intent.attemptedBefore = withdrawing and proof.withdrawAttempts or proof.attempted
        proposal.intent.maxAttempts = withdrawing and options.maxWithdrawAttempts or maximum
        proposal.intent.fromCollection=options.fromCollection
        proposal.intent.maxWithdraw,proposal.intent.maxWithdrawAttempts=options.maxWithdraw,options.maxWithdrawAttempts
        for _, field in ipairs({"scope", "selectedItemId", "excludedItems", "excludedKinds", "excludedRarities",
            "keepLoose", "maxQuantity", "minSales", "minUnits", "minNet", "likelyOnly", "undercutGold", "floorPct",
            "maxListings", "maxListAttempts"}) do proposal.intent[field] = options[field] end
        return proposal, nil
    end
    function owner:CaptureSale(proposal, before)
        if type(proposal) ~= "table" or proposal.feature ~= "marketSell"
            or type(proposal.intent) ~= "table" or type(before) ~= "table" then
            return nil, "Listing capture input unavailable"
        end
        for _, field in ipairs({"session", "account", "place", "release", "revision"}) do
            if proposal[field] ~= before[field] then return nil, "Listing capture snapshot changed" end
        end
        local context = {collectionProtection = before.collectionProtection}
        for _, field in ipairs(headers) do context[field] = before[field] end
        local view, reason = self:SaleView(before, context)
        if not view then return nil, reason end
        local options = {fromCollection = proposal.intent.fromCollection, maxWithdraw = proposal.intent.maxWithdraw, maxWithdrawAttempts = proposal.intent.maxWithdrawAttempts}
        for _, field in ipairs({"scope", "selectedItemId", "excludedItems", "excludedKinds", "excludedRarities",
            "keepLoose", "maxQuantity", "minSales", "minUnits", "minNet", "likelyOnly", "undercutGold", "floorPct",
            "maxListings", "maxListAttempts"}) do options[field] = proposal.intent[field] end
        local expected
        expected, reason = self:PlanSale(view, {enabled = true, custom = options})
        if not expected then return nil, reason end
        if proposal.actionKey ~= expected.actionKey then return nil, "Listing action identity changed" end
        for _, field in ipairs({"intent", "resources"}) do
            if type(proposal[field]) ~= "table" then return nil, "Listing payload missing" end
            for key, value in pairs(expected[field]) do
                if proposal[field][key] ~= value then return nil, "Listing payload changed" end
            end
            for key in pairs(proposal[field]) do
                if expected[field][key] == nil then return nil, "Unexpected listing payload field" end
            end
        end
        if proposal.intent.kind=="marketCollectionWithdraw" then
            local input={}
            for key,value in pairs(proposal) do input[key]=value end
            input.preflightOnly=true
            return deps.MarketCollectionWithdrawEvidence.capture(input,before)
        end
        return deps.MarketListEvidence.capture(proposal, before)
    end
    function owner:View(raw, context)
        if state.closed then return nil, "Market reader closed" end
        if not state.options then return nil, state.preferenceReason or "Market watch disabled" end
        if not scoped(raw, context) then return nil, "Market research snapshot changed or stale" end
        if not state.browse or not currentResearchScope(state.browse)
            or clock:Now() - state.browse.capturedAt > 15 then return nil, "Waiting for complete fresh Market pages" end
        local listings = deps.MarketListingsState.read(raw, context)
        state.ownedItems = {}
        if listings then for _, row in pairs(listings.listings) do state.ownedItems[row.item] = true end end
        local averages, histories, terms, ready = {}, {}, {}, 0
        local selected = selectedIds()
        for _, id in ipairs(selected) do
            averages[id], histories[id] = rap:Get(id), prices:Get(id)
            if averages[id] and histories[id] then ready = ready + 1 end
            terms[id] = catalog:SaleTerms(raw, items[id].rarity)
        end
        local filteredWatch = {assess = function(all, listingId, average, history, item, itemTerms, settings, now)
            if not deps.MarketSettings.allows(state.options, item) then return nil, "Item excluded by current Market filters" end
            return deps.MarketWatchOpportunity.assess(all, listingId, average, history, item, itemTerms, settings, now)
        end}
        local research, reason = deps.MarketResearchView.assess(state.browse, averages, histories,
            items, terms, state.options.watch, clock:Now(), filteredWatch, deps.MarketBrowse.matchesItemScope)
        if not research then return nil, reason end
        local aging, agingReason
        if listings then aging, agingReason = deps.MarketAgingReview.assess(listings, averages, state.options.aging, clock:Now()) end
        local result = {readOnly = true, sourceKey = deps.fingerprint:lower(), research = research,
            aging = aging, agingReason = agingReason, cachedResearch = true,
            researchedItems = ready, selectedItems = #selected, browseAge = clock:Now() - state.browse.capturedAt}
        for _, key in ipairs(headers) do result[key] = raw[key] end
        return result, nil
    end

    function owner:AcquisitionConfirmed()
        state.browse,state.nextPage,state.nextBrowseAt=nil,nil,0
        resetSale(state.saleOptions)
    end
    function owner:FlipView(raw,context)
        if state.closed or researchFeature~="marketFlip" or not scoped(raw,context) then return nil,"Current Flip research required" end
        return {raw=raw,context=context},nil
    end
    function owner:PlanFlip(view,settings,transactionOwner,existing)
        if state.closed or type(view)~="table" or not scoped(view.raw,view.context)
            or type(settings)~="table" or settings.enabled~=true then return nil,"Flip disabled or snapshot changed" end
        local raw=view.raw
        local usage=transactionOwner:BuyUsage()
        if not usage then return nil,"Owned buy allowance unavailable" end
        local active=transactionOwner:Active()
        local prepared=existing and active and active.kind=="buy" and active.stage=="prepared"
            and active.actionKey==existing.actionKey and active.sourceKey==deps.fingerprint
            and active.preparedGeneration==existing.intent.ownerGeneration
        local following=active and (active.kind=="buy" and active.stage=="observed"
            or active.kind=="list" and active.stage=="prepared" and active.origin and active.origin.kind=="buy"
                and existing and active.actionKey==existing.actionKey)
        if active and not prepared and not following then return nil,"Existing Market transaction requires completion" end
        local options={}
        for k,v in pairs(settings.custom or settings) do options[k]=v end
        options.enabled=true
        local projected,reason=deps.MarketSettings.project("marketFlip",options,
            {attempted=usage.attempted,spent=usage.spent,transactionOpen=active~=nil and not prepared})
        if not projected then return nil,reason end
        if following then
            if not transactionOwner:ListingAttempts("marketFlip") then return nil,"Flip listing allowance unavailable" end
            local tx,reason=transactionOwner:ListingContext(raw,clock:Now(),existing and existing.actionKey)
            if not tx then return nil,reason end
            if tx.listAttempts>=options.maxListAttempts then return nil,"Purchased-copy listing allowance exhausted" end
            local saleView
            saleView,reason=self:SaleView(raw,view.context)
            if not saleView then return nil,reason end
            local original=view.context.collectionProtection
            local held=original and original.reserved and original.reserved[tx.itemId]
            if type(held)~="number" or held<1 then return nil,"Purchased item reservation unavailable" end
            local adjusted,proof,reserved={},{},{}
            for k,v in pairs(view.context) do adjusted[k]=v end
            for k,v in pairs(original) do proof[k]=v end
            for k,v in pairs(original.reserved) do reserved[k]=v end
            reserved[tx.itemId]=held-1;proof.reserved=reserved;adjusted.collectionProtection=proof
            local custody
            custody,reason=deps.MarketSaleCustody.assess(raw,adjusted,tx.itemId,items[tx.itemId],
                {keepLoose=tx.beforeLoose,maxQuantity=1,fromCollection=false,blockedItems=projected.selection.blockedItems,
                    blockedKinds=projected.selection.blockedKinds,blockedRarities=projected.selection.blockedRarities})
            if not custody then return nil,reason end
            local listings=deps.MarketListingsState.read(raw,view.context)
            local terms=catalog:SaleTerms(raw,items[tx.itemId].rarity)
            local quote
            quote,reason=deps.MarketSaleQuote.assess(custody,saleView.rap,saleView.history,saleView.browse,listings,terms,
                {minSales=options.minSales,minUnits=options.minUnits,minNet=1,likelyOnly=options.requireCoverage,
                    undercutGold=options.undercutGold,floorPct=options.floorPct},clock:Now())
            if not quote then return nil,reason end
            local proposal
            proposal,reason=deps.MarketFlipListPreflight.assess(tx,custody,quote,listings,terms,projected.followupList,clock:Now())
            if not proposal then return nil,reason end
            proposal.preflightOnly=nil
            local i=proposal.intent
            for k,v in pairs(options) do if k~="enabled" then i[k]=v end end
            i.sourceKey=deps.fingerprint;i.ownerGeneration=active.kind=="list" and active.preparedGeneration or transactionOwner.generation+1
            i.attemptedBefore=transactionOwner:ListingAttempts("marketFlip");i.spentBefore=usage.spent
            i.copyAttemptsBefore=tx.listAttempts
            i.buyMaxAttempts=options.maxAttempts;i.maxAttempts=options.maxListAttempts
            proposal.resources={[i.itemId]=1}
            proposal.actionKey="market-flip-list:"..i.sourceKey..":"..tostring(i.ownerGeneration)..":"..i.itemId
            return proposal,nil
        end
        if not state.browse or clock:Now()-state.browse.capturedAt>15 then return nil,"Waiting for complete Flip browse" end
        local candidates={}
        for index,row in ipairs(state.browse.rows) do
            if index>100 then break end
            local item=items[row.item]
            if item and deps.MarketSettings.allows(projected,item)
                and (projected.selection.scope~="Selected item" or row.item==projected.selection.selectedItemId) then
                local terms=catalog:SaleTerms(raw,item.rarity)
                if terms then
                    terms.minLevel=catalog.minLevel
                    local quote=deps.MarketWatchOpportunity.assess(state.browse,row.id,rap:Get(row.item),prices:Get(row.item),
                        item,terms,projected.watch,clock:Now())
                    if quote then
                        local proposal=deps.MarketFlipPreflight.assess(quote,raw,view.context,terms,
                            projected.buyBudget,usage.spent,usage.attempted,clock:Now())
                        if proposal then candidates[#candidates+1]={proposal=proposal,margin=quote.margin} end
                    end
                end
            end
        end
        table.sort(candidates,function(a,b)
            if a.margin~=b.margin then return a.margin>b.margin end
            return tostring(a.proposal.intent.listingId)<tostring(b.proposal.intent.listingId)
        end)
        if #candidates==0 then return nil,"No current Flip candidate within filters, custody and limits" end
        local proposal=candidates[1].proposal
        proposal.preflightOnly=nil
        local i=proposal.intent
        i.sourceKey=deps.fingerprint;i.ownerGeneration=prepared and active.preparedGeneration or transactionOwner.generation+1
        i.attemptedBefore=usage.attempted;i.spentBefore=usage.spent
        for k,v in pairs(options) do if k~="enabled" then i[k]=v end end
        proposal.resources={gold_bar=i.quotedPrice}
        proposal.actionKey="market-buy:"..i.sourceKey..":"..tostring(i.ownerGeneration)..":"..tostring(i.listingId)
        return proposal,nil
    end
    function owner:CaptureFlip(p,before,transactionOwner)
        local options={}
        for _,key in ipairs({"scope","selectedItemId","excludedItems","excludedKinds","excludedRarities",
            "minSales","minUnits","minMargin","minMarginPct","undercutGold","floorPct","requireCoverage",
            "maxBuy","sessionBudget","goldReserve","maxAttempts","maxListAttempts"}) do options[key]=p.intent[key] end
        options.maxAttempts=p.intent.buyMaxAttempts or p.intent.maxAttempts
        local context={collectionProtection=before.collectionProtection}
        for _,key in ipairs(headers) do context[key]=before[key] end
        local view,reason=self:FlipView(before,context)
        if not view then return nil,reason end
        local expected
        expected,reason=self:PlanFlip(view,{enabled=true,custom=options},transactionOwner,p)
        if not expected or expected.actionKey~=p.actionKey then return nil,reason or "Flip action changed" end
        for _,part in ipairs({"intent","resources"}) do
            for k,v in pairs(expected[part]) do if p[part][k]~=v then return nil,"Flip payload changed" end end
            for k in pairs(p[part]) do if expected[part][k]==nil then return nil,"Unexpected Flip payload" end end
        end
        local input={}
        for k,v in pairs(p) do input[k]=v end
        input.preflightOnly=true
        if p.intent.kind=="marketList" then return deps.MarketListEvidence.capture(input,before) end
        return deps.MarketBuyEvidence.capture(input,before)
    end
    function owner:Descriptor()
        return {id = "marketWatch", reader = {read = function(raw, context) return self:View(raw, context) end},
            planner = {propose = function(view, settings)
                if type(settings) ~= "table" or settings.enabled ~= true then return nil, "Market watch disabled" end
                local research = view.research
                local report = "Market: " .. tostring(research.totalRows) .. " listings; "
                    .. tostring(research.opportunityCount) .. " research candidates; prices ready "
                    .. tostring(view.researchedItems) .. "/" .. tostring(view.selectedItems) .. " items"
                if (research.variantCount or 0) > 0 then
                    report = report .. "; " .. tostring(research.variantCount)
                        .. " upgraded variant(s); pricing and trading withheld"
                end
                if research.opportunities[1] then
                    local first = research.opportunities[1]
                    report = report .. "; " .. first.itemId .. " estimated margin " .. tostring(first.margin) .. " Gold"
                end
                if view.aging then report = report .. "; " .. tostring(#view.aging) .. " owned listings to review" end
                if research.truncated then report = report .. "; bounded partial coverage" end
                return nil, report
            end}, evidence = deps.MarketBlocked.watch}
    end
    function owner:SaleDescriptor()
        return {id = "marketSell", reader = {read = function(raw, context) return self:SaleView(raw, context) end},
            planner = {propose = function(view, settings)
                local preview, reason = owner:SalePreview(view, settings)
                if not preview then return nil, "Market sale " .. tostring(view.itemId) .. ": " .. tostring(reason) end
                return nil, "Market sale preview: " .. tostring(preview.custody.quantity)
                    .. " x " .. tostring(view.itemId) .. " at " .. tostring(preview.quote.ask)
                    .. " Gold; listing execution unfinished"
            end}, evidence = deps.MarketBlocked.trade}
    end
    function owner:Close()
        state.closed, state.options, state.browse, state.nextPage = true, nil, nil, nil
        state.saleOptions, state.saleRequest, state.saleBrowse = nil, nil, nil
        browse:Close(); pages:Close(); rap:Close(); prices:Close()
        saleBrowse:Close(); salePages:Close(); saleRap:Close(); salePrices:Close()
    end
    return owner
end
return MarketResearchController
