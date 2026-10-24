import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  createState,
  setEnabled,
  setPolicy,
  applyValues,
  pause,
  resume,
  stop,
  featureStatus,
} from "../preview/model.mjs";

const features = [
  { id: "jobs", policies: ["Balanced", "XP"] },
  { id: "combat", policies: ["Cautious", "Balanced", "Custom"], combat: true },
  { id: "properties", policies: ["Best value", "Most income", "Custom"] },
  { id: "marketSell", policies: ["Keep useful items", "Custom"] },
];

test("starts inert and honors explicit false on snapshot hydration", () => {
  let state = createState(features);
  assert.ok(Object.values(state.enabled).every((value) => value === false));
  state = setEnabled(state, "jobs", true);
  state = applyValues(state, { jobs: false, properties: true });
  assert.equal(state.enabled.jobs, false);
  assert.equal(state.enabled.properties, true);
});

test("rejects invalid controls without partially applying a profile", () => {
  const state = createState(features);
  assert.throws(
    () => applyValues(state, { jobs: true, mystery: true }),
    /Unknown/,
  );
  assert.equal(state.enabled.jobs, false);
  assert.throws(() => setEnabled(state, "jobs", "false"), /boolean/);
  assert.throws(() => setPolicy(state, "combat", "Guaranteed win"), /policy/);
});

test("stop clears selected activity and remains latched until explicit resume", () => {
  let state = stop(setEnabled(createState(features), "jobs", true));
  assert.equal(state.enabled.jobs, false);
  state = setEnabled(state, "jobs", true);
  assert.equal(featureStatus(state, features[0]).label, "Stopped");
  assert.equal(featureStatus(resume(state), features[0]).label, "Ready");
});

test("pause preserves local desired switches and resume reevaluates them", () => {
  const state = pause(setEnabled(createState(features), "properties", true));
  assert.equal(state.enabled.properties, true);
  assert.equal(featureStatus(state, features[2]).label, "Paused");
  assert.equal(featureStatus(resume(state), features[2]).label, "Ready");
});

test("native Jobs owner blocks its matching routine and not Properties", () => {
  let state = applyValues(createState(features), {
    jobs: true,
    properties: true,
  });
  state = { ...state, scenario: "nativeJobs" };
  assert.match(featureStatus(state, features[0]).reason, /Native Auto Jobs/);
  assert.equal(featureStatus(state, features[2]).label, "Ready");
});

test("low health blocks combat while unrelated work remains ready", () => {
  const state = {
    ...applyValues(createState(features), { combat: true, properties: true }),
    scenario: "lowHealth",
  };
  assert.equal(featureStatus(state, features[1]).label, "Waiting");
  assert.match(featureStatus(state, features[1]).reason, /health/);
  assert.equal(featureStatus(state, features[2]).label, "Ready");
});

test("closed Market and uncertain scenarios explain why work waits", () => {
  const state = applyValues(createState(features), {
    jobs: true,
    marketSell: true,
  });
  assert.match(
    featureStatus({ ...state, scenario: "closedMarket" }, features[3]).reason,
    /shop/,
  );
  assert.match(
    featureStatus({ ...state, scenario: "unconfirmed" }, features[0]).reason,
    /45-second/,
  );
});

test("changes create fresh state and never mutate previous settings", () => {
  const before = createState(features);
  const after = setPolicy(setEnabled(before, "jobs", true), "jobs", "XP");
  assert.equal(before.enabled.jobs, false);
  assert.equal(before.policies.jobs, "Balanced");
  assert.equal(after.policies.jobs, "XP");
});

test("catalog accounts for every legacy feature and keeps Custom bounded", () => {
  const catalog = JSON.parse(
    readFileSync(new URL("../preview/catalog.json", import.meta.url), "utf8"),
  );
  const parity = readFileSync(
    new URL("../docs/parity.md", import.meta.url),
    "utf8",
  );
  const baseline = parity
    .split("## Current feature IDs")[1]
    .split("## Controllers")[0];
  const ids = [...baseline.matchAll(/^\| `(\w+)` \|/gm)].map(
    (match) => match[1],
  );
  assert.equal(ids.length, 50);
  const controls = catalog.features.map((feature) => feature.id);
  assert.equal(new Set(controls).size, controls.length);
  assert.ok(ids.every((id) => controls.includes(id)));
  assert.equal(
    new Set(catalog.pages.map((page) => page.id)).size,
    catalog.pages.length,
  );
  assert.ok(catalog.features.every((feature) => feature.custom.length <= 6));
  assert.ok(
    catalog.features.every((feature) =>
      catalog.pages.some((page) => page.id === feature.page),
    ),
  );
});

test("each system owns its tab and all related fights stay in Combat", () => {
  const catalog = JSON.parse(
    readFileSync(new URL("../preview/catalog.json", import.meta.url), "utf8"),
  );
  const owners = {
    heists: ["heists", "heistCollect", "sabotage"],
    jobs: ["jobs"],
    operations: ["operations", "collect"],
    favors: ["favors"],
    combat: [
      "combat",
      "warCombat",
      "bosses",
      "bossShop",
      "familyBossAttacks",
      "familyBossClaims",
      "globalBossAttack",
      "globalBossClaim",
    ],
    crew: [
      "crew",
      "crewGear",
      "crewRoll",
      "crewSort",
      "crewHeal",
      "crewTrain",
      "crewHire",
      "crewHealItems",
    ],
    inventory: ["cosmetics", "chests", "restoratives"],
    collection: ["collectionDonate"],
    money: ["bank", "withdraw"],
    property: ["properties"],
    safehouse: ["safehouse"],
    prestige: ["prestige"],
    shop: ["shop"],
    blackMarket: [
      "marketWatch",
      "marketSell",
      "marketFlip",
      "marketRent",
      "marketManage",
    ],
    family: ["familyCash", "familyStamina", "familyGold"],
    territory: ["territoryWatch", "station", "residency"],
    contracts: ["contracts", "bonuses", "autoContracts"],
    trophies: ["trophies", "trophyFocus"],
    skills: ["skills"],
    rewards: ["playtime", "groupBonus", "monthlyRewards"],
    events: ["briefcases", "eventShop"],
  };
  const expected = Object.entries(owners).flatMap(([page, ids]) =>
    ids.map((id) => [id, page]),
  );
  assert.deepEqual(
    Object.fromEntries(catalog.features.map(({ id, page }) => [id, page])),
    Object.fromEntries(expected),
  );
  const pages = Object.fromEntries(
    catalog.pages.map((page) => [page.id, page]),
  );
  for (const id of [
    ...Object.keys(owners),
    "overview",
    "profiles",
    "settings",
    "activity",
  ]) {
    assert.ok(pages[id], `Missing dedicated tab: ${id}`);
    assert.ok(pages[id].symbol, `Missing navigation symbol: ${id}`);
  }
  for (const [id, label] of Object.entries({
    heists: "Heists",
    jobs: "Jobs",
    combat: "Combat",
    collection: "Collection",
    money: "Money",
    property: "Property",
    shop: "Shop",
    blackMarket: "Black Market",
  })) {
    assert.equal(pages[id].label, label);
  }
});

test("native and custom gear strategies cannot own the loadout together", () => {
  const catalog = JSON.parse(
    readFileSync(new URL("../preview/catalog.json", import.meta.url), "utf8"),
  );
  const initial = createState(catalog.features);
  const native = setEnabled(initial, "crew", true);
  const custom = setEnabled(native, "crewGear", true);
  assert.equal(custom.enabled.crew, false);
  assert.equal(custom.enabled.crewGear, true);
  assert.equal(native.enabled.crew, true);
  assert.equal(initial.enabled.crewGear, false);
  const off = setEnabled(custom, "crewGear", false);
  assert.equal(off.enabled.crew, false);
  assert.equal(off.enabled.crewGear, false);
  assert.equal(setEnabled(custom, "crew", true).enabled.crewGear, false);
});

test("profile hydration rejects conflicting gear owners atomically", () => {
  const catalog = JSON.parse(
    readFileSync(new URL("../preview/catalog.json", import.meta.url), "utf8"),
  );
  const initial = createState(catalog.features);
  assert.throws(
    () => applyValues(initial, { jobs: true, crew: true, crewGear: true }),
    /conflicting/i,
  );
  assert.equal(initial.enabled.jobs, false);
  const native = setEnabled(initial, "crew", true);
  const custom = applyValues(native, { crewGear: true });
  assert.equal(custom.enabled.crew, false);
  assert.equal(custom.enabled.crewGear, true);
  assert.deepEqual(
    applyValues(initial, { crew: false, crewGear: true }).enabled,
    applyValues(initial, { crewGear: true, crew: false }).enabled,
  );
});
