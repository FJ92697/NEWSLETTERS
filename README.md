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

## Operations

The isolated Droplet runs Ubuntu and Nginx. The collector runs under restricted account `newsletterd`; published issues live in `/var/lib/newsletters/issues`. Check logs with `sudo tail -n 100 /var/log/newsletters-daily.log` and services with `sudo systemctl status nginx cron`. To run manually: `cd /opt/newsletters && sudo /usr/bin/python3 newsletter.py --draft --publish-public`.