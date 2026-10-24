// Checks inert evidence and coverage only; never loads or executes saved Luau.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve } from "node:path";

const readJson = (path) => JSON.parse(readFileSync(path, "utf8"));
const root = new URL("../", import.meta.url);
const audit = readJson(new URL("docs/native-reuse-decisions.json", root));
const catalog = readJson(new URL("preview/catalog.json", root));
const baseline = readJson(
  new URL("docs/native-evidence-2026-10-20.json", root),
);
assert.equal(audit.native_version, baseline.native_version);
assert.equal(audit.place_sha256, baseline.place_sha256);
assert.equal(audit.live_verified, false);
assert.equal(
  audit.source_hash_basis,
  "UTF-8 source text, CRLF normalized to LF",
);
const decisions = audit.decisions;
assert.equal(new Set(decisions.map((row) => row.id)).size, decisions.length);
assert.deepEqual(
  decisions.map(({ id, page }) => ({ id, page })),
  catalog.features.map(({ id, page }) => ({ id, page })),
);
for (const row of [...decisions, ...audit.supporting_systems]) {
  assert.ok(row.decision && row.native && row.hub_role && row.gates, row.id);
  assert.ok(row.evidence.length, `Missing evidence for ${row.id}`);
  for (const key of row.evidence) assert.ok(audit.evidence[key], key);
}
const sourceDir = process.argv[2];
for (const [key, entry] of Object.entries(audit.evidence)) {
  assert.match(entry.sha256, /^[a-f0-9]{64}$/);
  assert.ok(Number.isInteger(entry.line) && entry.line > 0, key);
  assert.ok(entry.anchor && entry.source, key);
  assert.match(entry.file, /^[A-Za-z0-9_-]+\.lua$/);
  if (sourceDir) {
    const source = readFileSync(resolve(sourceDir, entry.file), "utf8").replace(
      /\r\n/g,
      "\n",
    );
    assert.equal(
      createHash("sha256").update(source).digest("hex"),
      entry.sha256,
      key,
    );
    assert.ok(source.split("\n")[entry.line - 1].includes(entry.anchor), key);
  }
}
assert.equal(
  new Set(audit.observed_pass_keys).size,
  audit.observed_pass_keys.length,
);
if (sourceDir) {
  const config = readFileSync(
    resolve(sourceDir, audit.evidence.passes.file),
    "utf8",
  );
  const passBlock = config.split("u1.GAMEPASSES = {")[1].split("};")[0];
  const actualKeys = [...passBlock.matchAll(/^\s+(\w+)\s*=/gm)].map(
    (match) => match[1],
  );
  assert.deepEqual(actualKeys.sort(), [...audit.observed_pass_keys].sort());
}
console.log(
  `${decisions.length} feature decisions, ${audit.supporting_systems.length} supporting systems, ${Object.keys(audit.evidence).length} evidence anchors checked${sourceDir ? " against local source hashes and lines" : " (metadata only)"}.`,
);
