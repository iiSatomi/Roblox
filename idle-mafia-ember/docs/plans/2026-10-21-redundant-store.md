# Crash-tolerant decoded-table store core

Status 2026-10-21: two-slot core and four offline tests complete;
304 Python/Lupa tests total. Executor primitives and single-writer
ownership remain open.

`Checkpoint` and `ProfileStore` expect atomic decoded-table `Read`
and `Write`. Add a generic two-slot adapter over injected
`ReadFile`, `WriteFile`, JSON `Encode`/`Decode` and SHA-256 `Hash`.
Name files only by a hash of the logical key. Each slot stores a
generation, key, encoded payload and digest. Read the newest valid
slot, recover from one corrupt/interrupted slot, and fail closed when
no valid slot survives. Write the inactive slot, read it back and
verify before reporting success. A failed write must never permit
request dispatch. Test restart/recovery and corruption.

This assumes a single writer and an underlying single-file write
which leaves the other slot untouched. Cross-process ownership,
actual executor file/JSON/SHA APIs and live reliability remain open.
