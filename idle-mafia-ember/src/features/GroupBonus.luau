-- One no-argument native bonus claim; membership was checked by the reader.
local GroupBonus = {}

function GroupBonus.propose(view, settings)
    if type(view) ~= "table" or type(settings) ~= "table" then
        return nil, "Missing Group bonus input"
    end
    if settings.enabled ~= true then return nil, "Group bonus disabled" end
    if type(view.groupId) ~= "number" or view.groupId < 1
        or view.groupId % 1 ~= 0 then
        return nil, "Invalid Group bonus identity"
    end
    return {
        session = view.session, account = view.account,
        place = view.place, release = view.release,
        revision = view.revision, feature = "groupBonus",
        actionKey = "groupBonus:" .. view.groupId,
        resources = {},
        intent = { kind = "groupBonusClaim", groupId = view.groupId },
    }, nil
end

return GroupBonus
