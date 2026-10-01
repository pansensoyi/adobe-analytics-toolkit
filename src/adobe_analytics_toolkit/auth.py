"""Adobe IMS OAuth Server-to-Server (client credentials) token provider."""

from __future__ import annotations

import time
from typing import Callable, Sequence

import httpx

IMS_TOKEN_URL = "https://ims-na1.adobelogin.com/ims/token/v3"
DEFAULT_SCOPES = ("openid", "AdobeID", "additional_info.projectedProductContext")


class OAuthServerToServer:
    """Fetches and caches an access token, refreshing it shortly before expiry."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scopes: Sequence[str] = DEFAULT_SCOPES,
        *,
        token_url: str = IMS_TOKEN_URL,
        refresh_margin: int = 300,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.client_id = client_id
        self._secret = client_secret
        self.scopes = list(scopes)
        self.token_url = token_url
        self.refresh_margin = refresh_margin
        self._http = httpx.Client(transport=transport, timeout=30)
        self._clock = clock
        self._token: str | None = None
        self._expires_at = 0.0

    def token(self) -> str:
        if self._token is None or self._clock() >= self._expires_at - self.refresh_margin:
            self._refresh()
        assert self._token is not None
        return self._token

    def _refresh(self) -> None:
        resp = self._http.post(
            self.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self._secret,
                "scope": ",".join(self.scopes),
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._expires_at = self._clock() + float(data.get("expires_in", 3600))
