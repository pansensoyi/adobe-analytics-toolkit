"""Fluent builder for Adobe Analytics 2.0 ranked report requests."""

from __future__ import annotations

import copy
from datetime import date, datetime, timedelta
from typing import Any, Union

DateLike = Union[str, date, datetime]


def _iso(d: DateLike) -> str:
    if isinstance(d, str):
        return d if "T" in d else f"{d}T00:00:00.000"
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%dT%H:%M:%S.000")
    return f"{d.isoformat()}T00:00:00.000"


def date_range(start: DateLike, end: DateLike, *, inclusive_end: bool = True) -> str:
    """Build an Adobe dateRange string. With ``inclusive_end`` a plain end date covers that whole day."""
    if inclusive_end and isinstance(end, date) and not isinstance(end, datetime):
        end = end + timedelta(days=1)
    elif inclusive_end and isinstance(end, str) and "T" not in end:
        end = date.fromisoformat(end) + timedelta(days=1)
    return f"{_iso(start)}/{_iso(end)}"


class ReportRequest:
    """Build the JSON body for ``POST /reports``.

    Example:
        ReportRequest("myrsid").dates("2026-09-01", "2026-09-30") \\
            .dimension("daterangeday").metrics("visits", "pageviews").limit(400)
    """

    def __init__(self, rsid: str) -> None:
        self._body: dict[str, Any] = {
            "rsid": rsid,
            "globalFilters": [],
            "metricContainer": {"metrics": []},
            "settings": {"limit": 50, "page": 0, "dimensionSort": "asc", "countRepeatInstances": True},
        }

    def dates(self, start: DateLike, end: DateLike, *, inclusive_end: bool = True) -> "ReportRequest":
        self._body["globalFilters"] = [f for f in self._body["globalFilters"] if f.get("type") != "dateRange"]
        self._body["globalFilters"].append({"type": "dateRange", "dateRange": date_range(start, end, inclusive_end=inclusive_end)})
        return self

    def segment(self, segment_id: str) -> "ReportRequest":
        self._body["globalFilters"].append({"type": "segment", "segmentId": segment_id})
        return self

    def dimension(self, dim: str) -> "ReportRequest":
        self._body["dimension"] = dim if dim.startswith("variables/") else f"variables/{dim}"
        return self

    def metrics(self, *metrics: str) -> "ReportRequest":
        container = self._body["metricContainer"]["metrics"]
        for m in metrics:
            mid = m if m.startswith("metrics/") or m.startswith("cm") else f"metrics/{m}"
            container.append({"columnId": str(len(container)), "id": mid})
        return self

    def limit(self, n: int) -> "ReportRequest":
        if not 1 <= n <= 50000:
            raise ValueError("limit must be between 1 and 50000")
        self._body["settings"]["limit"] = n
        return self

    def sort(self, direction: str) -> "ReportRequest":
        if direction not in ("asc", "desc"):
            raise ValueError("direction must be 'asc' or 'desc'")
        self._body["settings"]["dimensionSort"] = direction
        return self

    def page(self, n: int) -> "ReportRequest":
        self._body["settings"]["page"] = n
        return self

    @property
    def metric_ids(self) -> list[str]:
        return [m["id"] for m in self._body["metricContainer"]["metrics"]]

    def build(self) -> dict[str, Any]:
        if "dimension" not in self._body:
            raise ValueError("a dimension is required")
        if not self._body["metricContainer"]["metrics"]:
            raise ValueError("at least one metric is required")
        if not any(f.get("type") == "dateRange" for f in self._body["globalFilters"]):
            raise ValueError("a date range is required")
        return copy.deepcopy(self._body)
