from __future__ import annotations

import ipaddress
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from .config import settings


class LLMError(Exception):
    message = "Lokale KI-Antwort ist nicht verfuegbar."


class LLMConfigurationError(LLMError):
    message = "LLM ist nicht vollstaendig konfiguriert."


class LLMUnsafeBaseUrlError(LLMConfigurationError):
    message = "LLM_BASE_URL muss standardmaessig auf eine lokale Loopback-Adresse zeigen."


class LLMConnectionError(LLMError):
    message = "llama-server ist nicht erreichbar."


class LLMTimeoutError(LLMError):
    message = "llama-server hat nicht rechtzeitig geantwortet."


@dataclass(frozen=True)
class LLMStatus:
    configured: bool
    base_url: str
    model: str | None
    loopback_only: bool
    reachable: bool
    generation_available: bool
    last_error: str | None = None


def _is_loopback_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    lowered = hostname.lower()
    if lowered == "localhost":
        return True
    try:
        return ipaddress.ip_address(lowered).is_loopback
    except ValueError:
        return False


def validate_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise LLMUnsafeBaseUrlError
    if not _is_loopback_host(parsed.hostname):
        raise LLMUnsafeBaseUrlError
    return base_url.rstrip("/")


class LocalOpenAIProvider:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = validate_base_url(base_url or settings.llm_base_url)
        self.model = model if model is not None else settings.llm_model
        self.timeout_seconds = timeout_seconds or settings.llm_timeout_seconds
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self.base_url.strip())

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def status(self) -> LLMStatus:
        if not self.configured:
            return LLMStatus(
                configured=False,
                base_url=self.base_url,
                model=None,
                loopback_only=True,
                reachable=False,
                generation_available=False,
                last_error=LLMConfigurationError.message,
            )
        active_model = self.model or "qwen2.5-7b-instruct-q4_k_m"
        try:
            async with self._http_client() as client:
                response = await client.get(f"{self.base_url}/models", headers=self._headers())
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and "data" in data and isinstance(data["data"], list) and data["data"]:
                    first_model = data["data"][0].get("id") or data["data"][0].get("name")
                    if first_model:
                        active_model = first_model
        except httpx.TimeoutException:
            return self._failed_status(LLMTimeoutError.message)
        except httpx.HTTPError as exc:
            return self._failed_status(f"{LLMConnectionError.message} {exc}")
        return LLMStatus(
            configured=True,
            base_url=self.base_url,
            model=active_model,
            loopback_only=True,
            reachable=True,
            generation_available=True,
            last_error=None,
        )

    async def chat(self, messages: list[dict[str, str]], temperature: float = 0.1) -> str:
        if not self.configured:
            raise LLMConfigurationError
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        try:
            async with self._http_client() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError from exc
        except httpx.HTTPError as exc:
            raise LLMConnectionError from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMConnectionError("llama-server lieferte eine unerwartete Antwort.") from exc
        return str(content).strip()

    def _failed_status(self, error: str) -> LLMStatus:
        return LLMStatus(
            configured=True,
            base_url=self.base_url,
            model=self.model,
            loopback_only=True,
            reachable=False,
            generation_available=False,
            last_error=error,
        )

    @asynccontextmanager
    async def _http_client(self) -> AsyncIterator[httpx.AsyncClient]:
        if self._client is not None:
            yield self._client
            return
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            yield client


def provider_from_settings() -> LocalOpenAIProvider:
    return LocalOpenAIProvider()
