-- Read the same native crate luck rule used by the saved InventoryTab.
local NativeCrateLuckSource = {}

function NativeCrateLuckSource.new(rule, release)
    if type(rule) ~= "table"
        or type(rule.crateLuck) ~= "function"
        or type(release) ~= "string" or #release == 0 then
        return nil, "Current native crate luck rule required"
    end
    return { release = release,
        Read = function(_, native)
            return rule.crateLuck(native)
        end }, nil
end

return NativeCrateLuckSource
