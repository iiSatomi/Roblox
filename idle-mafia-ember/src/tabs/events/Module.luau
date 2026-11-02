-- Free Briefcases and separately budgeted, earned-medal Event Shop acquisition.
local EventsTab = {}
local Methods = {}
Methods.__index = Methods

function EventsTab.BuildUI(section, feature, bind, numeric)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "events"
        and (feature.id == "briefcases" or feature.id == "eventShop")
        and type(bind) == "function", "Invalid Events UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", feature.id .. ".enabled", {
        Text = "Allow " .. feature.label,
        Description = "Select this activity; the status below shows whether this entry can run it.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    local custom
    if feature.id == "eventShop" then
        numeric = numeric or {}
        custom = group:Group({ Text = "Offer and medal limits", Open = false })
        group:Description({ Text = "Earned medals only. Buys one inventory item or crate; it does not open or use the reward." })
        for _, field in ipairs(feature.custom) do
            local key = "eventShop.custom." .. field.id
            if field.type == "number" then
                numeric[key] = true
                bind(custom, "Input", key, { Text = field.label,
                    Default = tostring(field.value), FireOnBlur = true })
            else
                assert(field.type == "select", "Invalid Event Shop setting")
                bind(custom, "Dropdown", key, { Text = field.label,
                    Options = field.options, Default = field.value })
            end
        end
    end
    return { feature = feature, tabOwned = true,
        custom = custom,
        status = group:Status({ Text = "Activity",
            Default = feature.id == "eventShop" and "Off — select an available offer and set limits"
                or "Off — free picks only" }) }
end

function EventsTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.FreeBriefcasesState) == "table"
        and type(deps.FreeBriefcasesState.read) == "function"
        and type(deps.FreeBriefcases) == "table"
        and type(deps.FreeBriefcases.propose) == "function"
        and type(deps.FreeBriefcasesEvidence) == "table"
        and type(deps.FreeBriefcasesEvidence.capture) == "function"
        and type(deps.FreeBriefcasesEvidence.evaluate) == "function"
        and type(deps.EventShopBlocked) == "table"
        and type(deps.EventShopBlocked.read) == "function"
        and type(deps.EventShopBlocked.propose) == "function"
        and type(deps.EventShopBlocked.capture) == "function"
        and type(deps.EventShopBlocked.evaluate) == "function",
        "Missing Events tab modules")
    local source, buyer = deps.eventShopSource, nil
    if source ~= nil then
        assert(type(source) == "table" and type(source.Read) == "function" and type(source.Enrich) == "function"
            and type(source.CanDispatch) == "function" and type(source.Close) == "function"
            and source.sourceKey == deps.fingerprint and source.release == deps.release
            and type(deps.EventShopBuyer) == "table" and type(deps.EventShopBuyer.new) == "function",
            "Current native Event Shop source and buyer required")
        buyer = deps.EventShopBuyer.new(source)
    end
    return setmetatable({ id = "events", ownedProofs = {"eventShopProof"}, deps = deps, shopSource = source, buyer = buyer }, Methods)
end

function Methods:NewEventShopSource(definition, readAttributes)
    local d = self.deps
    if type(d.NativeEventShopSource) ~= "table" or type(d.NativeEventShopSource.new) ~= "function" then
        return nil, "Native Event Shop source module unavailable"
    end
    return d.NativeEventShopSource.new(definition, readAttributes, d.fingerprint, d.release)
end

function Methods:Enrich(snapshot)
    if self.shopSource then
        -- Missing shop attributes must not block free Briefcase picks.
        local enriched = self.shopSource:Enrich(snapshot)
        if enriched then return enriched end
    end
    return snapshot
end

function Methods:Close()
    if self.shopSource then self.shopSource:Close() end
end

function Methods:Descriptors()
    local d = self.deps
    return {
        { id = "briefcases", reader = d.FreeBriefcasesState,
            planner = d.FreeBriefcases,
            evidence = d.FreeBriefcasesEvidence },
        { id = "eventShop", reader = self.buyer or d.EventShopBlocked,
            planner = self.buyer or d.EventShopBlocked,
            evidence = self.buyer or d.EventShopBlocked,
            recoverSaved = self.buyer and self.buyer.recoverSaved,
            canDispatch = function(proposal)
                return self.shopSource ~= nil and self.shopSource:CanDispatch(proposal) == true
            end },
    }
end

return EventsTab
