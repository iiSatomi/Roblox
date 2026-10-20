// Local design state only. No Roblox, network, storage, timers or gameplay code.
function known(state, id) {
  if (!Object.hasOwn(state.enabled, id))
    throw new Error(`Unknown feature: ${id}`);
}

export function createState(features) {
  return {
    enabled: Object.fromEntries(features.map((feature) => [feature.id, false])),
    policies: Object.fromEntries(
      features.map((feature) => [
        feature.id,
        feature.policies?.[0] ?? "Recommended",
      ]),
    ),
    choices: Object.fromEntries(
      features.map((feature) => [feature.id, feature.policies ?? []]),
    ),
    paused: false,
    stopped: false,
    scenario: "normal",
  };
}

export function setEnabled(state, id, on) {
  known(state, id);
  if (typeof on !== "boolean") throw new Error("Switch value must be boolean");
  return { ...state, enabled: { ...state.enabled, [id]: on } };
}

export function setPolicy(state, id, value) {
  known(state, id);
  if (!state.choices[id].includes(value))
    throw new Error(`Unknown policy for ${id}`);
  return { ...state, policies: { ...state.policies, [id]: value } };
}

export function applyValues(state, values) {
  for (const [id, on] of Object.entries(values)) {
    known(state, id);
    if (typeof on !== "boolean")
      throw new Error("Switch value must be boolean");
  }
  return { ...state, enabled: { ...state.enabled, ...values } };
}

export function pause(state) {
  return { ...state, paused: true };
}
export function resume(state) {
  return { ...state, paused: false, stopped: false };
}
export function stop(state) {
  return {
    ...state,
    stopped: true,
    paused: false,
    enabled: Object.fromEntries(
      Object.keys(state.enabled).map((id) => [id, false]),
    ),
  };
}

export function featureStatus(state, feature) {
  if (!state.enabled[feature.id])
    return { label: "Off", reason: "Choose when this activity is allowed." };
  if (state.stopped)
    return {
      label: "Stopped",
      reason: "Explicit Resume is required after Emergency Stop.",
    };
  if (state.paused)
    return {
      label: "Paused",
      reason: "Your choices are kept. No new work starts.",
    };
  if (state.scenario === "unconfirmed")
    return {
      label: "Waiting",
      reason:
        "Observing a sent action until its 45-second deadline. A skip is not success.",
    };
  if (state.scenario === "nativeJobs" && feature.id === "jobs") {
    return {
      label: "Waiting",
      reason: "Native Auto Jobs owns this activity. The hub yields.",
    };
  }
  if (state.scenario === "lowHealth" && feature.combat) {
    return {
      label: "Waiting",
      reason: "Below your health floor. Other activities can continue.",
    };
  }
  if (
    state.scenario === "closedMarket" &&
    ["marketSell", "marketFlip"].includes(feature.id)
  ) {
    return {
      label: "Waiting",
      reason: "Your Market shop is closed. Renting has its own permission.",
    };
  }
  return {
    label: "Ready",
    reason: "Sample eligibility met. This preview sends no gameplay requests.",
  };
}
