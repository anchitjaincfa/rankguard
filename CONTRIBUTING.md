# Contributing

RankGuard is early. The best contributions are small, deterministic improvements to migration safety:

- parser fixtures for real crawler exports
- matching edge cases with tests
- redirect-chain validation cases
- report improvements that make review faster
- docs for specific migration platforms

## Development

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Run the sample workflow:

```bash
mkdir -p build
PYTHONPATH=src python3 -m rankguard plan \
  --old examples/old_sitemap.xml \
  --new examples/new_sitemap.xml \
  --redirects build/redirects.csv \
  --report build/migration-report.html \
  --json build/migration-report.json \
  --rules build/nginx-redirects.conf
```

## Design Rules

- Keep the OSS core local-first.
- Do not add runtime dependencies unless they remove meaningful complexity.
- Every suggested redirect needs a score and a reason.
- Tests should avoid external network calls.
- Avoid claims that RankGuard guarantees rankings.
