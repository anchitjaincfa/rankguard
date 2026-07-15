# RankGuard

RankGuard is a local-first SEO migration guardrail. Feed it an old sitemap or crawler export and a new sitemap or staging crawl. It proposes redirect mappings, scores the risk, exports redirect rules, and produces a launch report you can share with developers, SEO teams, and clients.

It is intentionally not a broad SEO suite. The first job is narrower and more painful: preserve search equity during Shopify, Webflow, WooCommerce, Magento, headless, CMS, or domain migrations.

## Why this exists

Google's migration guidance says to prepare a URL mapping, configure redirects, and monitor old and new URLs during a site move. In practice, teams often discover broken redirects only after traffic falls. RankGuard gives the migration team a repeatable pre-launch and post-launch checklist that can run locally against private crawl exports.

Existing crawlers such as Screaming Frog and Sitebulb are powerful general-purpose audit tools. RankGuard's wedge is an opinionated workflow for migrations:

- old URL inventory in
- new URL inventory in
- candidate redirect map out
- launch validation against live URLs
- prioritized failures and confidence scores

## Install

```bash
python3 -m pip install .
```

From a checkout, you can also run:

```bash
PYTHONPATH=src python3 -m rankguard --help
```

## Quick Start

Generate a redirect map and report:

```bash
PYTHONPATH=src python3 -m rankguard plan \
  --old examples/old_sitemap.xml \
  --new examples/new_sitemap.xml \
  --redirects build/redirects.csv \
  --report build/migration-report.html \
  --json build/migration-report.json
```

Export server rules:

```bash
PYTHONPATH=src python3 -m rankguard plan \
  --old examples/old_sitemap.xml \
  --new examples/new_sitemap.xml \
  --rules build/nginx-redirects.conf \
  --rules-format nginx
```

Validate a redirect CSV after launch:

```bash
PYTHONPATH=src python3 -m rankguard validate \
  --redirects build/redirects.csv \
  --report build/launch-report.html \
  --json build/launch-report.json
```

## Inputs

RankGuard accepts:

- XML sitemaps and sitemap indexes
- CSV, TSV, and semicolon-delimited crawler exports with a URL-like column such as `url`, `address`, `loc`, `old_url`, or `new_url`
- plain text files with one URL per line
- HTTP(S) URLs pointing to any of the above
- `-` for one `plan` input when you want to read URLs from standard input

Column matching is case-insensitive and ignores spaces, underscores, and hyphens, so headers like `Status Code`, `status_code`, and `HTTP Status` are recognized. CSV title columns such as `title`, `page_title`, or `h1` are used as extra matching signals when present. Duplicate URL rows are ignored after the first occurrence.

## CLI Behavior

`plan` prints a summary and exits `0` by default, even when some old URLs need manual mapping. Add `--fail-on-issues` when you want CI to exit `2` if old URLs remain unmatched. `validate` exits `2` when any live redirect check fails. Input and file errors are printed without a Python traceback and exit `1`.

## What Gets Flagged

- old URLs without confident new targets
- low-confidence mappings needing human review
- redirect targets shared by many old URLs
- orphaned new URLs that no old URL maps to
- live redirects that end in 4xx/5xx responses
- redirect chains and loops
- temporary redirects where permanent redirects are expected
- redirects whose final URL does not match the planned target

## Product Direction

RankGuard is the OSS core of a larger migration-risk product. The open source project should stay useful on its own: local files, deterministic reports, no required cloud account. Commercial layers can add scheduled monitoring, Search Console integrations, agency workspaces, approvals, and migration warranties. The project should not present itself as regulated insurance without proper underwriting and legal structure.

See [docs/idea-analysis.md](docs/idea-analysis.md) and [docs/build-plan.md](docs/build-plan.md).

## Development

Run tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Run the example:

```bash
mkdir -p build
PYTHONPATH=src python3 -m rankguard plan \
  --old examples/old_sitemap.xml \
  --new examples/new_sitemap.xml \
  --redirects build/redirects.csv \
  --report build/migration-report.html
```

## License

MIT
