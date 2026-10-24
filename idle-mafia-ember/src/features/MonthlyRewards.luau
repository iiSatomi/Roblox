-- One earned monthly claim; the native call takes no arguments.
local MonthlyRewards = {}

function MonthlyRewards.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing monthly claim input"
    end
    if settings.enabled ~= true then return nil, "Monthly claim disabled" end
    if type(view.month) ~= "string" or not view.month:match("^%d%d%d%d%-%d%d$")
        or type(view.today) ~= "number" or type(view.nextDay) ~= "number"
        or view.nextDay < 1 or view.nextDay > view.total then
        return nil, "Invalid monthly claim identity"
    end
    return {
        session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "monthlyRewards",
        actionKey = "monthly:" .. view.month .. ":" .. view.today
            .. ":" .. view.nextDay,
        resources = {},
        intent = { kind = "monthlyClaim", month = view.month,
            today = view.today, nextDay = view.nextDay },
    }, nil
end

return MonthlyRewards
