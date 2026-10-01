# adobe-analytics-toolkit

![CI](https://github.com/pansensoyi/adobe-analytics-toolkit/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)

Pull data out of **Adobe Analytics** without fighting the 2.0 Reporting API.

- **OAuth Server-to-Server auth** (the replacement for deprecated JWT credentials) with token caching and early refresh.
- **Fluent report builder** — dates, dimension, metrics (incl. calculated metrics `cm…`), segments, limit, sort — validated before the request goes out.
- **Auto-pagination** — follows `lastPage` and stitches every page together.
- **Tidy rows** — `{"item_id", "<dimension>", "<metric>": value}` dicts, or a pandas DataFrame with the `[pandas]` extra.
- **Retries** on `429`/`5xx`, honouring `Retry-After`.

> Unofficial library. Not affiliated with or endorsed by Adobe.

## Install

```bash
pip install "adobe-analytics-toolkit[pandas] @ git+https://github.com/pansensoyi/adobe-analytics-toolkit.git"
```

## Usage

```python
import os
from adobe_analytics_toolkit import AnalyticsClient, OAuthServerToServer, ReportRequest

auth = OAuthServerToServer(os.environ["ADOBE_CLIENT_ID"], os.environ["ADOBE_CLIENT_SECRET"])
aa = AnalyticsClient(auth, global_company_id=os.environ["ADOBE_COMPANY_ID"])

report = (
    ReportRequest("myreportsuite")
    .dates("2026-09-01", "2026-09-30")      # end date is inclusive
    .dimension("daterangeday")
    .metrics("visits", "pageviews", "orders")
    .limit(400)
)

rows = aa.run(report)       # list[dict]
df = aa.run_df(report)      # pandas.DataFrame
```

Discover what's available in a report suite:

```python
aa.dimensions("myreportsuite")
aa.metrics("myreportsuite")
```

## Credentials

Create an **OAuth Server-to-Server** credential in the Adobe Developer Console with the Adobe Analytics API added, and assign the integration to a product profile with access to your report suites. The global company id can be found via the Discovery API or in the Analytics UI.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
