-- One selected stat, bounded batch and reviewed native cost rules.
local SkillsTab = {}
local Methods = {}
Methods.__index = Methods

function SkillsTab.BuildUI(section, feature, bind, numeric)
    assert(type(section) == "table" and type(feature) == "table"
        and feature.page == "skills" and feature.id == "skills"
        and type(bind) == "function" and type(numeric) == "table"
        and type(feature.custom) == "table" and #feature.custom == 3,
        "Invalid Skills UI feature")
    local group = section:Group({ Text = feature.label,
        Description = feature.description, Open = true })
    bind(group, "Toggle", "skills.enabled", {
        Text = "Allow skill allocation",
        Description = "Select this activity for the prototype.",
        Default = false, RevertOnClose = true, RevertTo = false,
    })
    for _, field in ipairs(feature.custom) do
        local key = "skills.custom." .. field.id
        if field.id == "stat" then
            assert(field.type == "select", "Invalid Skill selector")
            bind(group, "Dropdown", key, { Text = field.label,
                Options = field.options, Default = field.value })
        else
            assert(field.type == "number"
                and (field.id == "maxAllocations"
                    or field.id == "batchSize"),
                "Invalid Skills limit")
            numeric[key] = true
            bind(group, "Input", key, { Text = field.label,
                Default = tostring(field.value), FireOnBlur = true })
        end
    end
    return { feature = feature, tabOwned = true,
        status = group:Status({ Text = "Activity",
            Default = "Off — UI only" }) }
end

function SkillsTab.new(deps)
    assert(type(deps) == "table"
        and type(deps.NativeSkillCatalog) == "table"
        and type(deps.NativeSkillCatalog.new) == "function"
        and type(deps.SkillsState) == "table"
        and type(deps.SkillsState.read) == "function"
        and type(deps.Skills) == "table"
        and type(deps.Skills.propose) == "function"
        and type(deps.SkillsEvidence) == "table"
        and type(deps.SkillsEvidence.capture) == "function"
        and type(deps.SkillsEvidence.evaluate) == "function",
        "Missing Skills tab modules")
    local catalog = deps.NativeSkillCatalog.new(deps.config,
        deps.fingerprint, deps.release)
    return setmetatable({ id = "skills", deps = deps,
        catalog = catalog }, Methods)
end

function Methods:Enrich(snapshot)
    return self.catalog:Enrich(snapshot)
end

function Methods:Descriptors()
    local d = self.deps
    return { { id = "skills", reader = d.SkillsState,
        planner = d.Skills, evidence = d.SkillsEvidence } }
end

return SkillsTab
