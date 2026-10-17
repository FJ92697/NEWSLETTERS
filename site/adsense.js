/* Loads Google AdSense Auto ads only after a valid publisher ID is configured. */
(() => {
  const client = window.WORLD_DESK_ADSENSE_CLIENT;
  if (typeof client !== "string" || !/^ca-pub-\d{16}$/.test(client)) return;

  const account = document.createElement("meta");
  account.name = "google-adsense-account";
  account.content = client;
  document.head.append(account);

  const script = document.createElement("script");
  script.async = true;
  script.crossOrigin = "anonymous";
  script.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(client)}`;
  document.head.append(script);
})();
