# World Desk newsletter

A source-linked global business and technology briefing site with automated daily collection. The public site serves static HTML through Nginx; a scheduled collector reads enabled RSS feeds and GDELT search results and publishes a headline-led issue at 06:00 America/New_York.

## Live service

- Site: https://161-35-103-204.sslip.io/
- Server: isolated DigitalOcean Droplet, NYC1, 2 vCPU / 4 GB RAM / 80 GB disk. The selected plan is $24/month before tax and optional services.
- Schedule: once per day, 06:00 America/New_York. The site is intended to run continuously; daily collection depends on the server, network, and upstream source availability.

## Automatic collection

The collector fetches enabled RSS feeds and runs up to two bounded GDELT Doc API searches per cycle: one combined OR query across configured topics and one broad U.S. comparison query. A short 429 retry happens only when the API supplies a usable `Retry-After` of 30 seconds or less. If GDELT is unavailable, RSS results can still be published; failed/empty collections preserve the prior public index. At most 50 records per GDELT query and 30 combined issue cards are processed. Review `sources.json` to manage feeds and topics.

This is a bounded, configured sample, not every news item worldwide, and cannot prove an item has never appeared in U.S. media. Search results can be incomplete or rate limited. GDELT's documented search supports boolean operators and multilingual monitoring, but coverage is not exhaustive: [GDELT DOC API overview](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/). Hosted API quotas can produce HTTP 429 responses, so this collector limits request volume: [GDELT API quota notes](https://blog.gdeltproject.org/behind-the-scenes-api-quotas-the-impact-of-a-fraction-of-a-qps/).

## Publication and business features

Public issues link to sources and do not reproduce full articles, RSS excerpts, or source images. Optional AI summaries paraphrase only collected headline/feed metadata. They require `OPENAI_API_KEY` and explicit `--ai` or `NEWSLETTER_AI_PUBLIC_SUMMARIES=true`; API use may incur charges. AI is disabled by default. Automated output is not independently fact-checked or reviewed by an editor. Confirm source terms and obtain permissions before expanding commercial reuse.

The system does not send email, collect signups, charge readers, accept sponsorship, or guarantee profit. The single Droplet has not been load-tested for millions of readers.

## Deployment and operations

The isolated Droplet runs Ubuntu, Nginx, and Python's standard library. The collector runs under restricted account `newsletterd`; public issues live in `/var/lib/newsletters/issues`, outside the Git checkout. The app fast-forwards from the public GitHub main branch before its daily collection. The installer refuses to replace an existing non-symlink `/var/www/newsletters` path. Run it only on the dedicated newsletter Droplet.

On the server, inspect logs with `sudo tail -n 100 /var/log/newsletters-daily.log`; check services with `sudo systemctl status nginx cron`. To manually run a collection: `cd /opt/newsletters && sudo /usr/bin/python3 newsletter.py --draft --publish-public`.
