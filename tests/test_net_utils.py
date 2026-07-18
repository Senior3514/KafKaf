import time

import httpx
import pytest

from kafkaf.core.skills.net_utils import TTLCache, get_with_retry


class TestGetWithRetry:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self, monkeypatch):
        calls = []

        async def fake_get(self, url, params=None, headers=None):
            calls.append(url)
            return httpx.Response(200, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
        response = await get_with_retry("https://example.com")
        assert response.status_code == 200
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_retries_on_transport_error_then_succeeds(self, monkeypatch):
        attempts = {"n": 0}

        async def fake_get(self, url, params=None, headers=None):
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise httpx.ConnectError("boom", request=httpx.Request("GET", url))
            return httpx.Response(200, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
        monkeypatch.setattr("kafkaf.core.skills.net_utils._RETRY_DELAYS", (0, 0))
        response = await get_with_retry("https://example.com")
        assert response.status_code == 200
        assert attempts["n"] == 2

    @pytest.mark.asyncio
    async def test_retries_on_5xx_then_succeeds(self, monkeypatch):
        attempts = {"n": 0}

        async def fake_get(self, url, params=None, headers=None):
            attempts["n"] += 1
            status = 503 if attempts["n"] < 2 else 200
            return httpx.Response(status, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
        monkeypatch.setattr("kafkaf.core.skills.net_utils._RETRY_DELAYS", (0, 0))
        response = await get_with_retry("https://example.com")
        assert response.status_code == 200
        assert attempts["n"] == 2

    @pytest.mark.asyncio
    async def test_never_retries_a_4xx(self, monkeypatch):
        attempts = {"n": 0}

        async def fake_get(self, url, params=None, headers=None):
            attempts["n"] += 1
            return httpx.Response(404, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
        response = await get_with_retry("https://example.com")
        assert response.status_code == 404
        assert attempts["n"] == 1

    @pytest.mark.asyncio
    async def test_propagates_the_exception_after_exhausting_retries(self, monkeypatch):
        async def fake_get(self, url, params=None, headers=None):
            raise httpx.ConnectError("boom", request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
        monkeypatch.setattr("kafkaf.core.skills.net_utils._RETRY_DELAYS", (0, 0))
        with pytest.raises(httpx.ConnectError):
            await get_with_retry("https://example.com")


class TestTTLCache:
    def test_set_then_get(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_missing_key_returns_none(self):
        cache = TTLCache(ttl_seconds=60)
        assert cache.get("missing") is None

    def test_expired_entry_returns_none_and_is_evicted(self):
        cache = TTLCache(ttl_seconds=10)
        cache.set("key", "value")
        cache._store["key"] = (time.monotonic() - 20, "value")
        assert cache.get("key") is None
        assert "key" not in cache._store
