# Security Policy

## Supported versions

Only the latest release receives fixes.

## Reporting a vulnerability

Email **fra.pall8o@gmail.com** with:

- a description of the issue and its impact,
- steps to reproduce,
- the version (`tecnocasa-mcp --version`) and client you used.

Please do not open a public issue for security reports. You should get a reply
within 7 days.

## Scope

In scope:

- code execution, path traversal, injection or dependency issues,
- leaking data beyond what the public Tecnocasa pages already expose,
- denial of service caused by the server itself (for example unbounded
  concurrency or cache growth).

Out of scope:

- upstream availability: 502s, WAF blocks, timeouts, or `www.tecnocasa.it`
  blackholing requests on some networks,
- accuracy, completeness or availability of listings,
- rate limiting or blocking applied by Tecnocasa to your own IP,
- anything requiring credentials, since this project has none.

## Data handling

The server is read-only, requires no authentication, and stores nothing on
disk. Only in-memory caches of public listing data are kept, bounded by entry
count and TTL.
