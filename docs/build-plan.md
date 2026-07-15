# Build Plan

## Product Principle

RankGuard should feel like a migration engineer in a box: deterministic, local, inspectable, and hard to fool. The system should never pretend that a probabilistic match is certain. Every generated redirect needs a score, reason, and review path.

## Architecture

The OSS core is a Python package with no runtime dependencies:

- `io.py`: load sitemaps, sitemap indexes, CSV crawler exports, and text URL lists
- `normalize.py`: canonical URL normalization, path segmentation, tokenization
- `matcher.py`: deterministic redirect candidate generation and server-rule export
- `validate.py`: post-launch redirect-chain validation
- `report.py`: HTML and JSON reporting
- `cli.py`: `rankguard plan` and `rankguard validate`

This should remain dependency-light until a real crawler, web UI, or Search Console integration justifies extra packages.

## Matching Strategy

The first matcher combines:

- exact normalized path
- same trailing slug
- path-sequence similarity
- shared URL tokens
- same top-level section
- optional title similarity
- small bonus for shared numeric/SKU tokens

Future versions should add:

- configurable synonym maps such as `/products/` to `/shop/`
- Search Console click weighting
- canonical target hints from staging crawls
- product SKU extraction
- embedding-based semantic matching as an optional plugin
- human approval state persisted as JSON or SQLite

## Launch Validation

The launch validator should be boring and evidence-driven. It sends `HEAD` requests with redirects disabled, falls back to `GET` when a server returns 405 or 501 for `HEAD`, records every hop, and treats HTTP error responses such as 404 or 500 as final statuses rather than transport failures.

Target comparison should normalize scheme, host, default ports, path shape, and tracking parameters while preserving meaningful query parameters. A planned target of `/collection?page=2` is not equivalent to `/collection?page=3`.

The current validator flags:

- missing redirects
- 4xx/5xx final URLs
- redirect loops
- redirect chains
- temporary redirects
- redirect responses with no `Location` header
- final-target mismatches

`RedirectValidation.ok` is false when any issue is present, including warnings. Severity communicates priority: `critical` means the migration target is broken or unverifiable, while `warning` means the redirect may work but still creates launch risk or cleanup work.

Future versions should validate canonical tags, robots directives, noindex headers, hreflang return tags, internal links, XML sitemap inclusion, and Search Console index status.

## Data Model

Keep the data model boring:

- `URLRecord`: URL plus optional title, status, canonical, source, metadata
- `RedirectCandidate`: old URL, new URL, score, confidence, reason, alternatives
- `MappingResult`: candidates, unmatched old URLs, orphan new URLs, many-to-one conflicts
- `RedirectValidation`: expected target, final target, status, hop chain, issues

## AI Usage

Use AI as an assistant, not authority:

- cluster unmatched URLs by likely migration pattern
- summarize launch issues in plain English
- generate client-facing explanations from deterministic evidence
- propose synonym rules from accepted human mappings

Avoid AI for:

- silent redirect decisions
- direct production rule deployment
- claims about Google ranking outcomes
- regulated insurance underwriting without a separate legal system

## Commercial System

Once the CLI is useful, build a hosted coordination layer:

1. Local agent runs crawls and uploads redacted metadata.
2. Web app manages approvals, owners, comments, and reports.
3. Search Console connector prioritizes URLs by clicks and impressions.
4. Scheduler runs launch-hour and post-launch checks.
5. Agency workspace produces branded client deliverables.

The local agent should remain able to run without the cloud.

## Reliability Bar

Every risky operation should be testable offline:

- parser fixtures for sitemaps and crawler CSVs
- matching unit tests for common migration patterns
- request-level validation tests for redirect chains, loops, missing locations, temporary redirects, query mismatches, and HEAD-to-GET fallback
- golden HTML/JSON report snapshots once the format stabilizes
- integration test for `rankguard plan` using sample files

RankGuard can be wrong, but it must be legibly wrong.
