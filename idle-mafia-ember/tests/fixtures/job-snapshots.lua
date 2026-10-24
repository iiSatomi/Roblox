-- Synthetic offline cases shaped by the cited client fields.
return {
    catalog = {
        { id = "j_watch", level = 1, energy = 1, cash = 60, xp = 2 },
        { id = "j_tag", level = 2, energy = 2, cash = 120, xp = 4 },
    },
    available = {
        level = 2, pools = { energy = 5 }, cash = 100, xp = 10,
        jobs = { j_watch = { completions = 3, masteryProgress = 3, masteryTier = 0 } },
        derived = { autoJobs = false },
    },
    locked = {
        level = 1, pools = { energy = 5 }, jobs = {},
        derived = { autoJobs = false },
    },
    lowEnergy = {
        level = 2, pools = { energy = 0 }, jobs = {},
        derived = { autoJobs = false },
    },
    nativeActive = {
        level = 2, pools = { energy = 5 }, jobs = {},
        derived = { autoJobs = true }, autoJob = { mode = "one", jobId = "j_watch" },
        autoJobCurrent = "j_watch", autoJobWaiting = false,
    },
    activityUnknown = {
        level = 2, pools = { energy = 5 }, jobs = {},
        -- Synthetic incomplete snapshot; the activity field is unavailable.
    },
    changedCatalog = {
        { id = "j_watch", level = 3, energy = 2, cash = 70, xp = 3 },
    },
}
