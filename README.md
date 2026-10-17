# World Desk newsletter

A small, source-linked global business and technology briefing site with a daily scheduled collector. The public site serves static HTML through Nginx; a cron job collects enabled RSS and GDELT search results and publishes a headline-led issue at 06:00 America/New_York.

## Live service

- Site: https://161-35-103-204.sslip.io/
- Server: a new DigitalOcean Droplet, NYC1, 2 vCPU / 4 GB RAM / 80 GB disk. The selected plan is $24/month before tax and any optional services.
- Schedule: once per day, 06:00 America/New_York. The server and site are intended to run continuously; daily publishing depends on upstream source availability.

## Deployment

The isolated Droplet runs Ubuntu, Nginx, and the Python standard library. `deploy/install.sh` clones this public repository, configures a static Nginx site, and installs the daily cron job. The collector runs under a restricted `newsletterd` account. Generated public issues are stored in `/var/lib/newsletters/issues`, outside the Git checkout, so publishing does not dirty deployment files or block future updates. The app checkout fast-forwards from the public GitHub main branch at 5:50 a.m. Eastern, before the 6:00 a.m. collection. The collector runs as `newsletterd`, and daily logs rotate weekly. Run the installer only on the dedicated newsletter Droplet. It refuses to replace an existing non-symlink `/var/www/newsletters` path.

## Coverage and publication limits

This is a bounded sample of enabled RSS and GDELT searches, not a worldwide archive or a guarantee that an item has never appeared in U.S. media. A missing U.S. search result is not proof of exclusive coverage. Search results can be incomplete or rate limited. Public issues never reproduce full source articles, RSS excerpts, or source images. They show source headlines and links; with `--ai --publish-public` and an `OPENAI_API_KEY`, they also include original short paraphrases based only on the collected headline/feed metadata. For scheduled publishing, set the secret `OPENAI_API_KEY` in the runtime environment and `NEWSLETTER_AI_PUBLIC_SUMMARIES=true`; this invokes the API on each scheduled run and may incur usage charges. When AI is off, cards remain headline-and-link leads. GDELT is credited in generated issues. Confirm source terms and obtain permissions before expanding commercial reuse. Automated output is not independently fact-checked or reviewed by an editor.

The current configuration does not send email, collect signups, charge readers, accept sponsorship, or generate guaranteed profit. AI is disabled by default; public AI summaries require either the explicit `--ai` flag or `NEWSLETTER_AI_PUBLIC_SUMMARIES=true`, plus an API key, and may incur API charges. No payment keys, banking details, or API secrets belong in this public repository. The single Droplet has not been load-tested for millions of readers.

## Operations

On the server, view the daily log with `sudo tail -n 100 /var/log/newsletters-daily.log`; check services with `sudo systemctl status nginx cron`. To manually run a collection: `cd /opt/newsletters && sudo /usr/bin/python3 newsletter.py --draft --publish-public`. An empty/failed collection leaves the previous issue list unchanged.


