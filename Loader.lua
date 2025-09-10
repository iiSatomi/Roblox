-- init.lua
local Rayfield = loadstring(game:HttpGet("https://sirius.menu/rayfield"))()

-- Setup window
local Window = Rayfield:CreateWindow({
    Name = "My Hub",
    LoadingTitle = "Loading...",
    LoadingSubtitle = "by You",
    ConfigurationSaving = { Enabled = true, FolderName = "MyHub", FileName = "Config" },
    KeySystem = false
})

-- Require modules
local modules = {"esp", "aimbot", "localplayer", "troll", "teleport"}
for _, mod in ipairs(modules) do
    local ok, result = pcall(function()
        return loadstring(game:HttpGet(""..mod..".lua"))()
    end)
    if not ok then
        warn("Failed to load module: "..mod, result)
    end
end
