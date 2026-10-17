# World Desk newsletter

A small, source-linked global business and technology briefing site with a daily scheduled collector. The public site serves static HTML through Nginx; a cron job collects enabled RSS and GDELT search results and publishes a headline-led issue at 06:00 America/New_York.

## Live service

- Site: http://161.35.103.204/
- Server: a new DigitalOcean Droplet, NYC1, 2 vCPU / 4 GB RAM / 80 GB disk. The selected plan is $24/month before tax and any optional services.
- Schedule: once per day, 06:00 America/New_York. The server and site are intended to run continuously; daily publishing depends on upstream source availability.

## Deployment

The isolated Droplet runs Ubuntu, Nginx, and the Python standard library. `deploy/install.sh` clones this public repository, configures a static Nginx site, and installs the daily cron job. Run it only on the new newsletter Droplet. It refuses to overwrite an existing non-symlink `/var/www/newsletters` path. It does not modify any other DigitalOcean server.

## Coverage and publication limits

This is a bounded sample of enabled RSS and GDELT searches, not a worldwide archive or a guarantee that an item has never appeared in U.S. media. A missing U.S. search result is not proof of exclusive coverage. Search results can be incomplete or rate limited. Public issues use headlines, source links, and short feed excerpts; they omit source images. GDELT is credited in generated issues. Confirm source terms and obtain permissions before expanding commercial reuse. Automated output is not independently fact-checked or reviewed by an editor.

The current configuration does not send email, collect signups, charge readers, accept sponsorship, or generate guaranteed profit. No OpenAI key is configured and AI is disabled by default. No payment keys, banking details, or API secrets belong in this public repository.

## Operations

On the server, view the daily log with `sudo tail -n 100 /var/log/newsletters-daily.log`; check services with `sudo systemctl status nginx cron`. To manually run a collection: `cd /opt/newsletters && sudo /usr/bin/python3 newsletter.py --draft --publish-public`. An empty/failed collection leaves the previous issue list unchanged.

