import json
from datetime import date
from urllib.parse import parse_qs

import httpx
import pytest

from adobe_analytics_toolkit import AnalyticsClient, OAuthServerToServer, ReportRequest, date_range


class StaticAuth:
    client_id = "cid"

    def token(self):
        return "tok"


def test_date_range_inclusive_end():
    assert date_range("2026-09-01", "2026-09-30") == "2026-09-01T00:00:00.000/2026-10-01T00:00:00.000"
    assert date_range(date(2026, 1, 1), date(2026, 1, 1)) == "2026-01-01T00:00:00.000/2026-01-02T00:00:00.000"
    assert date_range("2026-01-01", "2026-01-02", inclusive_end=False).endswith("2026-01-02T00:00:00.000")


def test_report_builder():
    body = (
        ReportRequest("rs1").dates("2026-09-01", "2026-09-30").dimension("daterangeday")
        .metrics("visits", "metrics/pageviews", "cm123_abc").segment("s300_x").limit(400).sort("desc").build()
    )
    assert body["dimension"] == "variables/daterangeday"
    assert [m["id"] for m in body["metricContainer"]["metrics"]] == ["metrics/visits", "metrics/pageviews", "cm123_abc"]
    assert [m["columnId"] for m in body["metricContainer"]["metrics"]] == ["0", "1", "2"]
    assert body["settings"]["limit"] == 400 and body["settings"]["dimensionSort"] == "desc"
    assert {"type": "segment", "segmentId": "s300_x"} in body["globalFilters"]


def test_dates_replaces_previous_range():
    r = ReportRequest("rs").dates("2026-01-01", "2026-01-31").dates("2026-02-01", "2026-02-28").dimension("page").metrics("visits")
    assert sum(f["type"] == "dateRange" for f in r.build()["globalFilters"]) == 1


@pytest.mark.parametrize("mutate", [lambda r: r.metrics("visits"), lambda r: r.dimension("page"), lambda r: r.dimension("page").metrics("visits")])
def test_builder_validation(mutate):
    r = ReportRequest("rs")
    if mutate is not None:
        mutate(r)
    with pytest.raises(ValueError):
        r.build()


def test_oauth_caches_and_refreshes():
    now = {"t": 1000.0}
    calls = []

    def handler(req):
        form = parse_qs(req.content.decode())
        calls.append(form)
        assert form["grant_type"] == ["client_credentials"]
        return httpx.Response(200, json={"access_token": f"t{len(calls)}", "expires_in": 3600})

    auth = OAuthServerToServer("cid", "secret", transport=httpx.MockTransport(handler), clock=lambda: now["t"])
    assert auth.token() == "t1"
    assert auth.token() == "t1"
    now["t"] += 3400  # within refresh margin
    assert auth.token() == "t2"
    assert len(calls) == 2


def test_run_paginates_and_flattens():
    pages = [
        {"rows": [{"itemId": "1", "value": "Home", "data": [10, 20]}], "lastPage": False},
        {"rows": [{"itemId": "2", "value": "Cart", "data": [3, 4]}], "lastPage": True},
    ]
    seen = []

    def handler(req):
        assert req.headers["x-api-key"] == "cid"
        assert req.headers["x-proxy-global-company-id"] == "acme0"
        assert req.headers["Authorization"] == "Bearer tok"
        body = json.loads(req.content)
        seen.append(body["settings"]["page"])
        return httpx.Response(200, json=pages[body["settings"]["page"]])

    client = AnalyticsClient(StaticAuth(), "acme0", transport=httpx.MockTransport(handler), sleep=lambda s: None)
    rows = client.run(ReportRequest("rs").dates("2026-09-01", "2026-09-30").dimension("page").metrics("visits", "pageviews"))
    assert seen == [0, 1]
    assert rows == [
        {"item_id": "1", "page": "Home", "visits": 10, "pageviews": 20},
        {"item_id": "2", "page": "Cart", "visits": 3, "pageviews": 4},
    ]


def test_retries_on_429():
    n = {"c": 0}

    def handler(req):
        n["c"] += 1
        return httpx.Response(429) if n["c"] == 1 else httpx.Response(200, json=[{"id": "variables/page"}])

    client = AnalyticsClient(StaticAuth(), "acme0", transport=httpx.MockTransport(handler), sleep=lambda s: None)
    assert client.dimensions("rs") == [{"id": "variables/page"}]
