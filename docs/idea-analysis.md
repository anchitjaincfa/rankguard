# Idea Analysis

## Source Signal

The email prompt described an ecommerce store migration where a broken redirect map can erase years of accumulated search rankings in days. The product concept was a tool that maps old URLs to new URLs before launch, validates staging mappings, and runs paired crawls immediately after go-live to surface 404s, redirect chains, and orphaned pages quickly.

## Core Customer Pain

The buyer is not buying "SEO software." They are buying protection against a specific high-consequence failure window:

- a Shopify, Magento, WooCommerce, Webflow, headless, or custom CMS migration
- a rebrand or domain change
- an agency handing redirects to a developer under deadline pressure
- an organic channel that matters enough that a 20% to 80% traffic loss would be material

The painful moment is concentrated. Teams know the launch date, know the stakes, and usually have messy crawl exports, multiple stakeholders, and no single source of truth for "which old URL should land where?"

## Why This Can Be a Startup

This is an attractive wedge because the failure is expensive, measurable, and embarrassing. Broad audit tools exist, but migration teams still assemble spreadsheets by hand because the workflow crosses SEO, engineering, platform configuration, client approval, and post-launch monitoring.

The product should start as a local-first power tool, not a generic SaaS dashboard. Crawl exports often contain private URLs, staging domains, unpublished product structures, and revenue-sensitive Search Console data. A downloadable OSS core also creates trust with agencies and technical SEOs.

## Competitive Landscape

- Screaming Frog SEO Spider is the incumbent desktop crawler. It audits broken links, redirects, redirect chains, robots directives, metadata, XML sitemaps, Google integrations, staging comparison, and more.
- Sitebulb and Lumar are broader technical SEO audit platforms.
- Monitoring tools such as Little Warden watch for domain, SSL, redirect, and HTTP-response changes.
- SEO suites such as Ahrefs, Semrush, and SE Ranking solve broader marketing workflows, not the migration control plane.

The opening is not "crawl better than Screaming Frog." The opening is "turn crawl exports into a migration control system": opinionated redirect generation, explicit approval states, launch validation, Search Console deltas, developer-ready rules, and an executive risk report.

## Product Wedge

RankGuard should own this sentence:

> "Before you flip the migration switch, RankGuard tells you which ranking URLs are still uninsured."

Use "insured" as positioning, not regulated insurance. The product can later support warranties or recovery guarantees, but actual insurance language needs legal and underwriting work.

## MVP

1. Ingest old sitemap or crawler export.
2. Ingest new sitemap or staging crawl.
3. Normalize URLs and score likely redirect targets.
4. Export CSV, nginx rules, and Apache rules.
5. Generate an HTML report with high-risk misses, confidence levels, and many-to-one targets.
6. Validate live redirects after launch with hop-by-hop status evidence, final-target comparison, and issue severity.

The open-source package in this repo implements those six pieces.

## Commercial Roadmap

- Hosted collaboration: review queues, approvals, comments, client sign-off.
- Search Console integration: prioritize old URLs by clicks, impressions, and backlinks.
- Migration timeline: pre-launch, launch-hour, 24-hour, 7-day, 30-day checks.
- CMS connectors: Shopify, Webflow, WordPress, Magento, BigCommerce.
- CI/CD integration: block deployment if redirect coverage drops.
- Agency workspaces: reusable templates, branded reports, client portals.
- Warranty layer: bounded recovery service or traffic-loss guarantee, only after legal review.

## Go-To-Market

Start with technical SEO consultants and ecommerce migration agencies. They already understand the problem, can test against historical migrations, and can make the tool part of a paid migration package.

Distribution loops:

- free OSS CLI for trust and data-sensitive teams
- migration postmortem templates
- "redirect map grader" content
- partner guides for Shopify, Webflow, and WooCommerce migrations
- agency-branded reports as a paid feature

## Risks

- Matching quality can be dangerously overtrusted. The UI must make confidence and review status explicit.
- Launch reports can be overread as ranking guarantees. They should show exact deterministic evidence: source URL, expected target, final URL, HTTP status, hop chain, issue code, and severity.
- Broad SEO tools can copy surface features. RankGuard needs workflow depth, not crawler breadth.
- Search Console integrations require careful OAuth and data retention design.
- "Insurance" positioning may trigger regulatory issues if converted into a financial guarantee.
- JavaScript-rendered sites and faceted ecommerce URLs can expand crawl scope quickly.

## Strong Opinion

Build the OSS core as a deterministic local CLI first. Reports should be useful because they cite specific URLs, statuses, redirects, and mismatches, not because they make broad promises about ranking outcomes. Add AI only where it reduces review labor: explain why a mapping was suggested, cluster low-confidence pages, and summarize launch failures. Do not let an LLM be the system of record for redirect decisions.
