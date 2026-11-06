# Idle Mafia anti-idle

`IdleMafiaAntiIdle.luau` is a standalone local input heartbeat, scoped to game
`10643795368` and place `73897506680154`. The manager installs the reviewed file
into Potassium's `autoexec` directory after live capability checks. It is separate
from the Ember release manifest and does not load a remote script.

It sends an initial input pulse, repeats every 60 seconds, and listens to
`LocalPlayer.Idled` as a fallback. Pulses are at least five seconds apart. Each
pulse calls `VirtualUser:CaptureController()` and
`VirtualUser:ClickButton2(Vector2.new(0, 0), workspace.CurrentCamera.CFrame)`.
Three consecutive failures stop the helper and warn in the executor console.
Rerunning the file stops its previous instance and replaces its listener/timer.
Early autoexec waits up to 30 seconds total for initially unknown game/place IDs
and `LocalPlayer`. A known different experience exits immediately. A previous
instance must report `running = false` after its `Stop()` before replacement.

Inspect or stop the current instance:

```lua
getgenv().__IdleMafiaAntiIdle:Status()
getgenv().__IdleMafiaAntiIdle:Stop()
```

`Status()` reports attempts, successful API calls, consecutive failures, the last
error, and the stopping reason. A successful API call does not establish that
Roblox reset its idle classification. Roblox documents that
[Player.Idled](https://create.roblox.com/docs/reference/engine/classes/Player)
starts roughly two minutes after idle classification and repeats every 30
seconds. Roblox's maintained
[VirtualUser source documentation](https://github.com/Roblox/creator-docs/blob/main/content/en-us/reference/engine/classes/VirtualUser.yaml)
describes limited playback reliability and lists no public methods. Executor
capability and actual session stability therefore require live verification.
The helper does not intercept native reconnect logic or promise that a session
will never disconnect.

Offline verification from `idle-mafia-ember/`:

```powershell
python -m pytest tests/test_anti_idle.py -q
```
