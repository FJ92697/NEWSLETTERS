/* Script status is diagnostic only; script loading does not prove ad delivery. */
(() => {
  const status = value => document.documentElement.setAttribute("data-adsense-state", value);
  const client = window.WORLD_DESK_ADSENSE_CLIENT;
  if (typeof client !== "string" || !/^ca-pub-\d{16}$/.test(client)) {
    status("not-configured");
    return;
  }

  const account = document.querySelector('meta[name="google-adsense-account"]') || document.createElement("meta");
  account.name = "google-adsense-account";
  account.content = client;
  if (!account.parentNode) document.head.append(account);

  if (window.WORLD_DESK_ADSENSE_ENABLED !== true) {
    status("awaiting-activation");
    return;
  }
  if (document.getElementById("world-desk-adsense")) return;

  const script = document.createElement("script");
  script.id = "world-desk-adsense";
  script.async = true;
  script.crossOrigin = "anonymous";
  script.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(client)}`;
  script.onload = () => status("script-loaded");
  script.onerror = () => status("script-unavailable");
  status("script-requested");
  document.head.append(script);
})();
