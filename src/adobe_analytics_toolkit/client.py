"""Adobe Analytics 2.0 API client with pagination and tidy output."""

from __future__ import annotations

import time
from typing import Any, Callable, Iterator, Protocol

import httpx

from .report import ReportRequest

API_BASE = "https://analytics.adobe.io/api"


class TokenProvider(Protocol):
    client_id: str

    def token(self) -> str: ...


class AnalyticsClient:
    """Client bound to one Adobe Analytics company (global company id)."""

    def __init__(
        self,
        auth: TokenProvider,
        global_company_id: str,
        *,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.auth = auth
        self.company = global_company_id
        self.max_retries = max_retries
        self._sleep = sleep
        self._http = httpx.Client(base_url=f"{API_BASE}/{global_company_id}", timeout=120, transport=transport)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.auth.token()}",
            "x-api-key": self.auth.client_id,
            "x-proxy-global-company-id": self.company,
            "Accept": "application/json",
        }

    def request(self, method: str, path: str, **kw: Any) -> Any:
        for attempt in range(self.max_retries + 1):
            resp = self._http.request(method, path, headers=self._headers(), **kw)
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < self.max_retries:
                    retry_after = resp.headers.get("Retry-After", "")
                    self._sleep(float(retry_after) if retry_after.isdigit() else 2**attempt)
                    continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("unreachable")

    # --------------------------------------------------------------- discovery
    def dimensions(self, rsid: str) -> list[dict[str, Any]]:
        return self.request("GET", "/dimensions", params={"rsid": rsid})

    def metrics(self, rsid: str) -> list[dict[str, Any]]:
        return self.request("GET", "/metrics", params={"rsid": rsid})

    # ----------------------------------------------------------------- reports
    def iter_pages(self, report: ReportRequest) -> Iterator[dict[str, Any]]:
        """Yield every page of a ranked report until ``lastPage`` is true."""
        page = 0
        while True:
            body = report.page(page).build()
            data = self.request("POST", "/reports", json=body)
            yield data
            if data.get("lastPage", True):
                return
            page += 1

    def run(self, report: ReportRequest) -> list[dict[str, Any]]:
        """Run a report across all pages and return tidy rows.

        Each row: ``{"item_id", "<dimension>", "<metric>": value, ...}``.
        """
        dim = report.build()["dimension"].split("/", 1)[1]
        names = [m.split("/", 1)[-1] for m in report.metric_ids]
        rows: list[dict[str, Any]] = []
        for page in self.iter_pages(report):
            rows.extend(flatten_rows(page, dim, names))
        return rows

    def run_df(self, report: ReportRequest):  # pragma: no cover - thin wrapper
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError("pip install 'adobe-analytics-toolkit[pandas]'") from e
        return pd.DataFrame(self.run(report))


def flatten_rows(page: dict[str, Any], dimension_name: str, metric_names: list[str]) -> list[dict[str, Any]]:
    out = []
    for r in page.get("rows", []):
        row: dict[str, Any] = {"item_id": r.get("itemId"), dimension_name: r.get("value")}
        row.update(zip(metric_names, r.get("data", [])))
        out.append(row)
    return out
