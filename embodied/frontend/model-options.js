export function profileReady(profile) {
  return !!(
    profile?.url &&
    profile.model &&
    (!["jev", "claude"].includes(profile.provider) || profile.key_configured)
  );
}

export function storageLabel(storage) {
  return storage?.persistent ? "Securely saved locally" : "Saved only in this service process";
}

export function storageDescription(storage) {
  if (storage?.persistent)
    return "Configuration saved locally, Key Protected by system keychain. Refresh page or restart service to continue using.";
  const message =
    storage?.message || "Currently only saved in service process; reconfiguration required after service restart.";
  return message.includes("Refresh page")
    ? message
    : `${message} Refresh page will not lose configuration.`;
}

export function selectionConfig(value, profiles) {
  if (!value.startsWith("profile:")) return { provider: value };
  const profile = profiles.find((item) => item.id === value.slice(8));
  if (!profile) throw new Error("Model configuration is invalid, please reselect.");
  return { provider: profile.provider, profile_id: profile.id };
}

export function selectionOptions(config, profiles, escape) {
  const defaults = config.providers
    .map(
      (provider) =>
        `<option value="${escape(provider.id)}" ${provider.ready ? "" : "disabled"}>${escape(provider.name)}${provider.ready ? "" : " · Not configured"}</option>`,
    )
    .join("");
  const saved = profiles
    .map(
      (profile) =>
        `<option value="profile:${escape(profile.id)}" ${profileReady(profile) ? "" : "disabled"}>${escape(profile.name)} · ${escape(profile.model)}${profileReady(profile) ? "" : " · Not configured"}</option>`,
    )
    .join("");
  return (
    defaults +
    (saved ? `<optgroup label="Saved model configuration">${saved}</optgroup>` : "")
  );
}
