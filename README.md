# World Desk newsletter

A source-linked, general-interest daily briefing for readers of different ages. It collects enabled RSS sources and global GDELT results across world affairs, public safety, health, science, space, climate, technology, education, culture, sports, business, and human-interest topics.

## Live service

- Site: https://161-35-103-204.sslip.io/
- Schedule: one automatic publication each day at 6:00 a.m. America/New_York on the dedicated DigitalOcean Droplet.

## Collection and ranking

Each daily run reads enabled RSS feeds and makes up to two bounded GDELT DOC API calls: one global search using the configured topic list, and one U.S. comparison search. GDELT is asked for up to 250 results per request, using its hybrid relevance ranking, which considers text relevance and outlet popularity. The publisher interleaves RSS and GDELT items, removes exact URL and normalized headline duplicates, and publishes up to 50 source-linked stories. These limits keep a daily issue readable while retrieving a larger candidate pool. A 429 is retried once only when the service supplies a short `Retry-After` value; if GDELT is unavailable, RSS collection can continue and the issue displays a source availability note.

GDELT says DOC searches support OR queries across monitored languages and its Article List can return up to 250 results. Its relevance ranking considers outlet popularity as one factor; this is not an editorial judgment or a guarantee that every important story will appear. Coverage is incomplete, and the system cannot prove that a story has not appeared in U.S. media. [GDELT DOC API documentation](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/).

The current RSS source is Hacker News, a community feed focused on technology, and should be treated as only one input. GDELT provides the wider general-interest discovery. The configured topics are in `sources.json` and can be adjusted there.

## Publication limits

Public issues link to original reporting and show headlines, source names, and links. They do not republish full articles, RSS excerpts, or source images. Optional AI summaries require `OPENAI_API_KEY` and explicit `--ai` or `NEWSLETTER_AI_PUBLIC_SUMMARIES=true`; usage may incur API charges. AI remains off by default. Headlines and generated summaries are not independently fact-checked or reviewed by an editor. Check each publisher’s terms and obtain permission before adding feeds or reusing their material in a commercial product.

## Free reading and advertising setup

The homepage and issues are free to read. AdSense Auto ads support is installed but inactive until a real publisher ID is configured. To activate it:

1. Apply for an AdSense account and add the live site URL in AdSense. Google reviews the whole site; ads cannot serve until its status is **Ready**.
2. Put the genuine `ca-pub-...` publisher ID into `site/adsense-config.js`, then publish that change. Keep `WORLD_DESK_ADSENSE_ENABLED = false` during setup. Use the exact verification method supplied by Google; if it requires a static meta tag, add that exact tag to the homepage head. The loader is included on the homepage and every generated issue.
3. Add Google's account-provided seller line to `site/ads.txt` once the account supplies it, then deploy. Do not use a guessed publisher ID or ads.txt entry.
4. Complete identity, tax, payment, and privacy/consent setup in AdSense. Revenue depends on eligible ad impressions, audience, advertiser demand, location, and policy compliance. Google does not guarantee payment for every page access. Never ask readers to click ads.
5. Add the owner's confirmed public publisher name and contact details. Update the current privacy notice for the selected provider and configure the provider-supported consent system where required. When the site is approved, enable Auto ads in the provider dashboard and set `WORLD_DESK_ADSENSE_ENABLED = true`. Update the About page's advertising status at the same time.

The loader rejects malformed IDs, prevents duplicate script insertion, and exposes a `data-adsense-state` attribute on the HTML element for diagnostics. `script-loaded` only confirms that the library loaded; it does not prove a rendered advertisement, billable impression, or payment.

Run `python audit_ads.py` for a bounded read-only live configuration report. Exit code 2 means configuration remains incomplete. Run `python -m unittest -v` and `node --test test_adsense.cjs` for offline checks; the JavaScript tests use a fake DOM and make no ad requests. Verify a real ad with a single ordinary browser visit after approval, without clicking it or repeatedly refreshing. Confirm impressions, payment eligibility, and payout settings separately in the provider dashboard.

No additional paid service or expedited payout has been enabled. AdSense is free to join and pays monthly. Adcash advertises daily auto-billing, but its standard NET+1 payment option deducts 10% (minimum USD/EUR 10). These are separate settings; account-specific promotions can differ. Existing DigitalOcean hosting still has its own cost. Do not activate every network together: Mediavine requires exclusive programmatic inventory, and other agreements can also restrict combinations. Use only exact tags and ads.txt entries issued to this publisher by an approved provider; do not invent IDs or integration URLs.

Official references: [AdSense participation](https://support.google.com/adsense/answer/32850?hl=en), [AdSense review](https://support.google.com/adsense/answer/7584263?hl=en), [Adcash payment setup](https://adcash.com/blog/adcash-publisher-platform-guide/), [Mediavine exclusivity](https://help.mediavine.com/why-mediavine-requires-exclusivity).

AdSense approval is not guaranteed. The current issue format is mostly source-linked headlines, so Google may consider pages to have too little original publisher content. Publish useful original reporting or commentary and a privacy policy before applying. See Google's [site review instructions](https://support.google.com/adsense/answer/7584263?hl=en) and [publisher policies](https://support.google.com/adsense/answer/10502938?hl=en&topic=1271507), which disallow monetizing low-value or replicated pages.

## Operations

The isolated Droplet runs Ubuntu and Nginx. The collector runs under restricted account `newsletterd`; published issues live in `/var/lib/newsletters/issues`. Check logs with `sudo tail -n 100 /var/log/newsletters-daily.log` and services with `sudo systemctl status nginx cron`. To run manually: `cd /opt/newsletters && sudo /usr/bin/python3 newsletter.py --draft --publish-public`.

## WordPress connection

The opt-in WordPress publisher is implemented and covered by offline tests. It has not been connected to a live WordPress installation. It does not install WordPress, buy hosting, modify another website, activate ads, or change the existing schedule.

Use a separate WordPress installation under the hosting plan that has an available website slot. On the new site, use a dedicated Author account and its revocable application password. Supply `WORDPRESS_SITE_URL`, `WORDPRESS_USERNAME`, and `WORDPRESS_APPLICATION_PASSWORD` as runtime environment variables to the collector; never commit credentials. `WORDPRESS_SITE_URL` is the exact final HTTPS site address, including a WordPress subdirectory if applicable. Redirects are refused to prevent forwarding authentication credentials.

`WORDPRESS_STATE_DIR` selects a persistent directory writable by the collector. The default is `private/wordpress-state`, ignored by Git. Keep it between deployments and include it in private backups. Run only one collector/state directory for each WordPress site.

With those values configured:

```bash
# Create a private draft first and inspect its blocks in WordPress.
python newsletter.py --draft --wordpress draft

# For normal daily publication after the live setup has been verified:
python newsletter.py --draft --publish-public --wordpress publish
```

Each date has one deterministic issue slug. Repeat runs read and preserve an existing matching issue rather than overwrite editorial changes. A draft is not silently promoted to a published post: publish that reviewed draft in WordPress before using `--wordpress publish` for the same date. Future dates create new posts automatically when the command is added to the scheduler.

The integration authenticates the author, checks permissions, creates core paragraph/heading blocks, and reads the saved post back to check its status and content. Source excerpts and images are excluded. Original AI summaries are optional and require the existing AI setting and API credentials. No AI call is enabled by adding WordPress alone.

If a write has an uncertain outcome, a durable pending marker blocks another create. A later run can reconcile a matching post through a read. If it cannot, inspect the WordPress posts, drafts, and trash before clearing that single issue's marker. Never delete the whole state directory to bypass an error. A stale `.lock` file likewise needs confirmation that the earlier publisher has stopped before removal. The lock protects one collector host, not multiple independent servers.

Ad configuration is separate from posting. The static site's disabled AdSense files do not automatically install an ad integration in WordPress. Use the approved publisher's official WordPress integration, actual publisher ID, required consent configuration, and site approval before enabling ads. Site traffic and earnings require separate dashboard evidence.

Official API references: [WordPress posts](https://developer.wordpress.org/rest-api/reference/posts/), [application password authentication](https://developer.wordpress.org/rest-api/using-the-rest-api/authentication/), and [current user permissions](https://developer.wordpress.org/rest-api/reference/users/).
