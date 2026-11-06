-- Read-only Market research and earned payout, with Gold trades blocked.
local BlackMarketTab = {}
local Methods = {}
Methods.__index = Methods

local blocked = {
    marketSell = "Market trade runtime and shared item reservations are not connected",
    marketFlip = "Market trade runtime and shared item reservations are not connected",
}
local known = { marketWatch = true, marketSell = true,
    marketFlip = true, marketRent = true, marketManage = true }

function BlackMarketTab.BuildUI(section, feature, bind, numeric, recovery)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "blackMarket" and known[feature.id]
        and type(bind) == "function"
        and type(numeric) == "table",
        "Invalid Black Market UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    local reason = blocked[feature.id]
    local isTrade=feature.id=="marketSell" or feature.id=="marketFlip"
    local recoveryAvailable = isTrade and type(recovery) == "table" and recovery.available == true
    if recoveryAvailable then
        reason = nil
        group:Description({Text=feature.id=="marketFlip" and "Buys one qualifying listing with ordinary Gold, then lists only that acquired item. Pause to review saved work or release a confirmed purchase hold." or "Lists owned loose items and separately opted-in unbound Collection surplus. Pause to review saved work or release a confirmed withdrawal hold."})
    end
    if reason then group:Description({ Text = reason }) end
    local custom = group:Group({ Text = "Selection and limits", Open = false })
    for _, field in ipairs(feature.custom) do
        local key = feature.id .. ".custom." .. field.id
        if field.type == "number" or field.type == "text" then
            numeric[key] = field.type == "number" or nil
            bind(custom, "Input", key, { Text = field.label,
                Default = tostring(field.value), FireOnBlur = true })
        elseif field.type == "boolean" then
            bind(custom, "Toggle", key, { Text = field.label,
                Default = field.value })
        else
            assert(field.type == "select" and type(field.options) == "table",
                "Invalid Market custom control")
            bind(custom, "Dropdown", key, { Text = field.label,
                Default = field.value, Options = field.options })
        end
    end
    local row = { feature = feature, tabOwned = true,
        custom = custom,
        blockedReason = reason,
        status = group:Status({ Text = "Activity",
            Default = reason and "Blocked — " .. reason
                or "Off — UI only" }) }
    if isTrade then
        local controls = group:Group({Text="Saved listing recovery",Open=false,
            Disabled=not recoveryAvailable,DisabledReason="Recovery requires a compatible runtime"})
        controls:Description({Text="Pause, review the exact saved listing, then confirm local cleanup. No sale, retry or allowance reset."})
        row.recoveryStatus=controls:Status({Text="Saved listing",Save=false,FireOnStart=false,
            Default=recoveryAvailable and "Pause to review a saved listing" or "Recovery unavailable in this entry"})
        local function user(origin)
            return not origin or not (origin.initial or origin.restored or origin.reapplied or origin.reverted)
        end
        local function alive() return recoveryAvailable and type(recovery.alive)=="function" and recovery.alive() end
        row.recoveryReview=controls:Button({Text="Review saved listing",ButtonText="Review",FireOnStart=false,
            Callback=function(_,_,origin)
                if not alive() or not user(origin) then return end
                local ok,preview,why=pcall(recovery.preview)
                if not alive() then return end
                row.recoveryStatus:Set(ok and type(preview)=="table" and (tostring(preview.itemId)..": "..preview.description)
                    or (ok and (why or "No reviewable listing") or "Listing recovery review failed"),true)
            end})
        row.recoveryConfirm=controls:Button({Text="Confirm local listing cleanup",ButtonText="Confirm cleanup",
            Danger=true,FireOnStart=false,Callback=function(_,_,origin)
                if not alive() or not user(origin) then return end
                local ok,saved,why=pcall(recovery.confirm)
                if not alive() then return end
                row.recoveryStatus:Set(ok and saved==true and "Local cleanup saved; automation remains paused"
                    or (ok and (why or "Cleanup refused") or "Listing cleanup failed"),true)
            end})
    end
    return row
end

function BlackMarketTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.MarketEarningsState) == "table"
        and type(deps.MarketEarningsState.read) == "function"
        and type(deps.MarketEarnings) == "table"
        and type(deps.MarketEarnings.propose) == "function"
        and type(deps.MarketEarningsEvidence) == "table"
        and type(deps.MarketEarningsEvidence.capture) == "function"
        and type(deps.MarketEarningsEvidence.evaluate) == "function"
        and type(deps.MarketBrowse) == "table"
        and type(deps.MarketBrowse.new) == "function"
        and type(deps.MarketPrices) == "table"
        and type(deps.MarketPrices.new) == "function"
        and type(deps.MarketRap) == "table"
        and type(deps.MarketRap.new) == "function"
        and type(deps.MarketListingsState) == "table"
        and type(deps.MarketListingsState.read) == "function"
        and type(deps.MarketSaleCustody) == "table"
        and type(deps.MarketSaleCustody.assess) == "function"
        and type(deps.MarketSaleQuote) == "table"
        and type(deps.MarketSaleQuote.assess) == "function"
        and type(deps.MarketBrowsePages) == "table"
        and type(deps.MarketBrowsePages.new) == "function"
        and type(deps.MarketListEvidence) == "table"
        and type(deps.MarketListEvidence.capture) == "function"
        and type(deps.MarketListEvidence.evaluate) == "function"
        and type(deps.MarketRentQuote) == "table"
        and type(deps.MarketRentQuote.assess) == "function"
        and type(deps.MarketRentEvidence) == "table"
        and type(deps.MarketRentEvidence.capture) == "function"
        and type(deps.MarketRentEvidence.evaluate) == "function"
        and type(deps.NativeMarketCatalog) == "table"
        and type(deps.NativeMarketCatalog.new) == "function"
        and type(deps.MarketWatchOpportunity) == "table"
        and type(deps.MarketWatchOpportunity.assess) == "function"
        and type(deps.MarketResearchView) == "table"
        and type(deps.MarketResearchView.assess) == "function"
        and type(deps.MarketTransactions) == "table"
        and type(deps.MarketTransactions.new) == "function"
        and type(deps.MarketSettings) == "table"
        and type(deps.MarketSettings.project) == "function"
        and type(deps.MarketSettings.allows) == "function"
        and type(deps.MarketAgingReview) == "table"
        and type(deps.MarketAgingReview.assess) == "function"
        and type(deps.MarketFlipPreflight) == "table"
        and type(deps.MarketFlipPreflight.assess) == "function"
        and type(deps.MarketBuyEvidence) == "table"
        and type(deps.MarketBuyEvidence.capture) == "function"
        and type(deps.MarketBuyEvidence.evaluate) == "function"
        and type(deps.MarketFlipListPreflight) == "table"
        and type(deps.MarketFlipListPreflight.assess) == "function"
        and type(deps.MarketCollectionWithdrawPreflight) == "table"
        and type(deps.MarketCollectionWithdrawPreflight.assess) == "function"
        and type(deps.MarketCollectionWithdrawEvidence) == "table"
        and type(deps.MarketCollectionWithdrawEvidence.capture) == "function"
        and type(deps.MarketCollectionWithdrawEvidence.evaluate) == "function"
        and type(deps.MarketSellListPreflight) == "table"
        and type(deps.MarketSellListPreflight.assess) == "function"
        and type(deps.MarketSellDirectPreflight) == "table"
        and type(deps.MarketSellDirectPreflight.assess) == "function"
        and type(deps.MarketReadRuntime) == "table"
        and type(deps.MarketReadRuntime.new) == "function"
        and type(deps.MarketBlocked) == "table"
        and type(deps.MarketBlocked.watch) == "table"
        and type(deps.MarketBlocked.trade) == "table",
        "Missing Black Market tab modules")
    local self = setmetatable({ id = "blackMarket", deps = deps, ownedProofs = {"marketRentTermsProof", "marketSellOwnerProof"} }, Methods)
    if type(deps.MarketRentRuntime) == "table" then self.rent = deps.MarketRentRuntime.new(deps) end
    if type(deps.config) == "table" and type(deps.config.MARKET) == "table"
        and type(deps.fingerprint) == "string" and type(deps.release) == "string" then
        self.rentCatalog = deps.NativeMarketCatalog.new(deps.config, deps.fingerprint, deps.release)
    end
    if type(deps.MarketResearchController) == "table" and type(deps.clock) == "table"
        and type(deps.identity) == "table" and type(deps.config) == "table"
        and type(deps.config.MARKET) == "table" then
        self.research = deps.MarketResearchController.new(deps)
        local flipDeps={}
        for key,value in pairs(deps) do flipDeps[key]=value end
        flipDeps.researchFeature="marketFlip"
        self.flipResearch=deps.MarketResearchController.new(flipDeps)
    end
    if deps.storage ~= nil and deps.identity ~= nil then
        self.transactions, self.transactionFault = self:NewTransactions(deps.storage, deps.identity)
        if not self.transactions and not self.transactionFault then self.transactionFault = "Market custody owner unavailable" end
        if type(deps.MarketPayoutLedger) == "table" then
            self.payoutLedger, self.payoutFault = deps.MarketPayoutLedger.new(deps.storage, deps.identity, deps.MarketEarningsEvidence)
        end
        if not self.payoutLedger then self.payoutFault = self.payoutFault or "Durable payout ledger unavailable" end
    end
    if type(deps.MarketSellRuntime) == "table" then
        self.sellRuntime = deps.MarketSellRuntime.new(deps, self.transactions, self.research)
        self.flipRuntime=deps.MarketSellRuntime.new(deps,self.transactions,self.flipResearch,"marketFlip")
    end
    return self
end

function Methods:ReservationSources()
    return {{id = "marketTransactions", read = function()
        if self.closed then return nil, "Market owner closed" end
        if self.transactionFault then return nil, self.transactionFault end
        if not self.transactions then return nil end -- Inert composition has no storage.
        return self.transactions:ReservationClaims()
    end}}
end

function Methods:Close()
    self.closed = true
    if self.sellRuntime then self.sellRuntime:Close() end
    if self.flipRuntime then self.flipRuntime:Close() end
    if self.research then self.research:Close() end
    if self.flipResearch then self.flipResearch:Close() end
    if self.payoutLedger then self.payoutLedger:Close() end
    if self.transactions and type(self.transactions.Close) == "function" then self.transactions:Close() end
end

function Methods:ReadSources()
    local sources=self.research and self.research:Sources() or {}
    if self.flipResearch then
        for _,source in ipairs(self.flipResearch:Sources()) do sources[#sources+1]=source end
    end
    return sources
end

function Methods:Enrich(snapshot)
    if type(snapshot) ~= "table" then return snapshot, nil end
    local out = {}
    for key, value in pairs(snapshot) do out[key] = value end
    out.marketRentTermsProof = nil
    out.marketSellOwnerProof = nil
    if not self.closed and self.rentCatalog then
        local value = self.rentCatalog:RentTerms(snapshot)
        if value then
            local proof = {terms = value}
            for _, field in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do proof[field] = snapshot[field] end
            out.marketRentTermsProof = proof
        end
    end
    snapshot = out
    if self.closed or not self.transactions or self.transactionFault or type(snapshot) ~= "table"
        or type(snapshot.native) ~= "table" or snapshot.native.fullSync ~= true then return snapshot, nil end
    for _, field in ipairs({"session", "account", "place", "release"}) do
        if type(self.deps.identity) ~= "table" or snapshot[field] ~= self.deps.identity[field] then return snapshot, nil end
    end
    local function attachOwnerProof()
        local attempted = self.transactions:ListingAttempts()
        if attempted == nil then return snapshot end
        local proof = {attempted = attempted, withdrawAttempts=self.transactions:WithdrawAttempts(), generation = self.transactions.generation,
            transactionOpen = self.transactions:Active() ~= nil}
        for _, field in ipairs({"session", "account", "place", "release", "revision", "capturedAt"}) do
            proof[field] = snapshot[field]
        end
        snapshot.marketSellOwnerProof = proof
        return snapshot
    end
    local active = self.transactions:Active()
    if not active then return attachOwnerProof(), nil end
    local stamp = self.recoveryStamp
    if stamp and stamp.session == snapshot.session and stamp.revision == snapshot.revision
        and stamp.capturedAt == snapshot.capturedAt then return attachOwnerProof(), nil end
    self.recoveryStamp = {session = snapshot.session, revision = snapshot.revision, capturedAt = snapshot.capturedAt}
    -- Store reconciliation is state-only. Prepared/recovered sent records are
    -- never submitted here; exact observed intermediates retain their custody.
    local ok, outcome, reason = pcall(self.transactions.Reconcile, self.transactions, snapshot)
    self.recoveryOutcome = ok and outcome or "uncertain"
    self.recoveryReason = ok and reason or "Market recovery observation raised"
    return attachOwnerProof(), nil
end

function Methods:ProjectSettings(feature, options, runState)
    return self.deps.MarketSettings.project(feature, options, runState)
end

function Methods:AllowsItem(projected, item)
    return self.deps.MarketSettings.allows(projected, item)
end

function Methods:NewResearch(budget, executor, clock, onResult)
    local d = self.deps
    return d.MarketReadRuntime.new(budget,
        d.MarketBrowse.new(5, clock), d.MarketPrices.new(clock),
        executor, onResult, d.MarketRap.new(clock))
end

function Methods:NewTransactions(storage, scope)
    return self.deps.MarketTransactions.new(storage,
        scope, self.deps.MarketListEvidence,
        self.deps.MarketCollectionWithdrawEvidence,
        self.deps.MarketBuyEvidence)
end

function Methods:ReadListings(raw, context)
    return self.deps.MarketListingsState.read(raw, context)
end

function Methods:NewBrowsePages()
    return self.deps.MarketBrowsePages.new(5, 500)
end

function Methods:AssessSaleCustody(raw, context, id, item,
    settings, tiers)
    return self.deps.MarketSaleCustody.assess(raw, context,
        id, item, settings, tiers)
end

function Methods:AssessSaleQuote(custody, rap, history, browse,
    listings, terms, settings, now)
    return self.deps.MarketSaleQuote.assess(custody, rap, history,
        browse, listings, terms, settings, now)
end

function Methods:ListEvidence()
    return self.deps.MarketListEvidence
end

function Methods:AssessRent(raw, context, terms, settings, attempted)
    return self.deps.MarketRentQuote.assess(raw, context,
        terms, settings, attempted)
end

function Methods:RentEvidence()
    return self.deps.MarketRentEvidence
end

function Methods:NewMarketCatalog(config, fingerprint, release)
    return self.deps.NativeMarketCatalog.new(config,
        fingerprint, release)
end

function Methods:AssessOpportunity(browse, listingId, rap,
    history, item, terms, settings, now)
    return self.deps.MarketWatchOpportunity.assess(browse,
        listingId, rap, history, item, terms, settings, now)
end

function Methods:AssessResearch(browse, rapByItem,
    historyByItem, itemsById, termsByItem, settings, now)
    return self.deps.MarketResearchView.assess(browse,
        rapByItem, historyByItem, itemsById, termsByItem,
        settings, now, self.deps.MarketWatchOpportunity)
end

function Methods:ReviewAgingListings(listings, rapByItem,
    settings, now)
    return self.deps.MarketAgingReview.assess(listings,
        rapByItem, settings, now)
end

function Methods:AssessFlip(browse, listingId, rap, history,
    item, terms, watchSettings, raw, context, budget,
    spent, attempted, now)
    local quote, reason = self:AssessOpportunity(browse,
        listingId, rap, history, item, terms, watchSettings, now)
    if not quote then return nil, reason end
    return self.deps.MarketFlipPreflight.assess(quote,
        raw, context, terms, budget, spent, attempted, now)
end

function Methods:BuyEvidence()
    return self.deps.MarketBuyEvidence
end

function Methods:AssessFlipList(tx, custody, quote,
    listings, terms, settings, now)
    return self.deps.MarketFlipListPreflight.assess(tx,
        custody, quote, listings, terms, settings, now)
end

function Methods:AssessCollectionWithdraw(custody,
    quote, listings, terms, settings, attempted, now)
    return self.deps.MarketCollectionWithdrawPreflight.assess(
        custody, quote, listings, terms, settings,
        attempted, now)
end

function Methods:CollectionWithdrawEvidence()
    return self.deps.MarketCollectionWithdrawEvidence
end

function Methods:AssessSellAfterWithdraw(tx, custody, quote,
    listings, terms, settings, now)
    return self.deps.MarketSellListPreflight.assess(tx,
        custody, quote, listings, terms, settings, now)
end

function Methods:AssessDirectSale(custody, quote, listings,
    terms, settings, attempted, now)
    return self.deps.MarketSellDirectPreflight.assess(
        custody, quote, listings, terms, settings,
        attempted, now)
end

function Methods:Descriptors()
    local d = self.deps
    local watch = self.research and self.research:Descriptor()
        or { id = "marketWatch", reader = d.MarketBlocked.watch,
            planner = d.MarketBlocked.watch, evidence = d.MarketBlocked.watch }
    local sell = self.research and self.research:SaleDescriptor()
        or { id = "marketSell", reader = d.MarketBlocked.trade,
            planner = d.MarketBlocked.trade, evidence = d.MarketBlocked.trade }
    if self.sellRuntime then
        local runtime = self.sellRuntime
        sell = {id="marketSell",reader=runtime,planner=runtime,evidence=runtime,
            lifecycle=runtime.lifecycle,recoverSaved=runtime.recoverSaved,canDispatch=runtime.canDispatch}
    end
    return {
        watch,
        sell,
        self.flipRuntime and {id="marketFlip",reader=self.flipRuntime,planner=self.flipRuntime,evidence=self.flipRuntime,
            lifecycle=self.flipRuntime.lifecycle,recoverSaved=self.flipRuntime.recoverSaved,canDispatch=self.flipRuntime.canDispatch}
            or {id="marketFlip",reader=d.MarketBlocked.trade,planner=d.MarketBlocked.trade,evidence=d.MarketBlocked.trade},
        { id = "marketRent", reader = self.rent or d.MarketBlocked.trade,
            planner = self.rent or d.MarketBlocked.trade, evidence = self.rent or d.MarketBlocked.trade,
            recoverSaved = self.rent and self.rent.recoverSaved,
            canDispatch = function() return not self.closed and self.rentCatalog ~= nil and self.rent ~= nil end },
        { id = "marketManage", reader = d.MarketEarningsState,
        planner = d.MarketEarnings,
        evidence = d.MarketEarningsEvidence, recoverSaved = d.MarketEarningsEvidence.recoverSaved,
        canDispatch = function() return not self.closed and self.payoutLedger ~= nil and self.payoutFault == nil end,
        recordOutcome = function(data, after)
            if self.closed or not self.payoutLedger or self.payoutFault then return false, self.payoutFault or "Payout ledger unavailable" end
            return self.payoutLedger:Record(data, after)
        end },
    }
end

return BlackMarketTab
