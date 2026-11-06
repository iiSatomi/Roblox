# Two-slot decoded-table storage core

`RedundantStore` implements the decoded-table `Read`/`Write`
interface expected by `Checkpoint` and `ProfileStore`. It accepts
injected file reads/writes, JSON encode/decode, SHA-256 and a local
directory. The injected `ReadFile` must return `nil` for a missing
file and raise on an I/O failure. Logical keys become SHA-256
filenames. Each of two slots
stores a generation, the logical key, encoded payload and digest.
In default profile mode, `Read` chooses the newest valid slot and one
corrupt slot falls back to the other. A checkpoint ledger must instead
use `RedundantStore.new(..., { strictRecovery = true })`; `Checkpoint.new`
requires every checkpoint storage adapter to declare
`strictRecovery = true`; missing or false declarations are rejected. Strict mode raises when either
slot is corrupt, because that slot might hold a newer sent attempt.
Rolling back to an older ledger could allow a duplicate action. A
file-read error and two invalid slots also fail closed. `Write` updates the inactive slot
and verifies it by reading it back before returning success.

This is an offline core, not a production executor adapter. It
assumes one writer and that a write to one file cannot damage the
other slot. The actual executor's file, JSON and SHA-256 APIs,
directory creation, cross-process ownership and persistence across
client restarts need integration and live verification. The
distributed Ember 0.1.1 build still injects no storage and remains
inert.

Offline tests cover both profile fallback and strict checkpoint refusal
after a damaged write. Current full-suite evidence is in the handoff.
