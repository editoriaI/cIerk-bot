from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


class PriceLookupProvider(Protocol):
    def lookup(self, item: str) -> dict[str, Any]:
        ...


PriceStatus = Literal["found", "not_found", "backend_error", "timeout", "error"]


@dataclass
class PriceLookupResult:
    status: PriceStatus
    payload: dict[str, Any] | None = None
    detail: str | None = None


def read_timeout_env(name: str, default: float, minimum: float = 1.0) -> float:
    raw = os.getenv(name, "")
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(minimum, value)


def configure_logging(app_name: str, level: int = logging.INFO) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    out_path = LOG_DIR / f"{app_name}.out.log"
    err_path = LOG_DIR / f"{app_name}.err.log"

    if not _has_handler(root_logger, logging.FileHandler, out_path):
        out_handler = logging.FileHandler(out_path, encoding="utf-8")
        out_handler.setLevel(level)
        out_handler.setFormatter(formatter)
        root_logger.addHandler(out_handler)

    if not _has_handler(root_logger, logging.FileHandler, err_path):
        err_handler = logging.FileHandler(err_path, encoding="utf-8")
        err_handler.setLevel(logging.ERROR)
        err_handler.setFormatter(formatter)
        root_logger.addHandler(err_handler)

    if not any(h.__class__ is logging.StreamHandler for h in root_logger.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)


def _has_handler(logger: logging.Logger, handler_type: type, target_path: Path) -> bool:
    for handler in logger.handlers:
        if isinstance(handler, handler_type) and getattr(handler, "baseFilename", None) == str(target_path):
            return True
    return False


async def perform_price_lookup(
    pricing: PriceLookupProvider,
    item: str,
    timeout: float,
    logger: logging.Logger,
) -> PriceLookupResult:
    try:
        payload = await asyncio.wait_for(
            asyncio.to_thread(pricing.lookup, item),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.warning("price lookup timed out item=%s", item)
        return PriceLookupResult(status="timeout")
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("price lookup failed item=%s", item)
        return PriceLookupResult(status="error", detail=f"{type(exc).__name__}: {exc}")

    if not payload.get("found"):
        if payload.get("error"):
            logger.warning(
                "pricing backend errors item=%s count=%s samples=%s",
                item,
                payload.get("error_count"),
                payload.get("error_samples"),
            )
            return PriceLookupResult(
                status="backend_error",
                payload=payload,
                detail=payload.get("error"),
            )
        return PriceLookupResult(status="not_found", payload=payload)

    return PriceLookupResult(status="found", payload=payload)


def build_price_response_text(
    result: PriceLookupResult,
    item: str,
    timeout: float,
) -> str:
    if result.status == "timeout":
        return (
            f"Pricing check timed out after {timeout:.0f}s. "
            "The pricing API may be down."
        )
    if result.status == "error":
        detail = result.detail or "unknown error"
        return f"Pricing check failed: {detail}"
    if result.status == "backend_error":
        error = result.payload.get("error") if result.payload else None
        attempts = result.payload.get("error_count", 0) if result.payload else 0
        if error:
            return f"Pricing is currently unavailable: {error} (tried {attempts} feeds)."
        return "Pricing feed is currently unavailable. Please try again soon."
    if result.status == "not_found":
        return f"No fresh price found for '{item}'. Try #ItemName or recent selling context."
    if result.status == "found" and result.payload:
        data = result.payload
        return (
            f"Price check: {data['item']} -> avg ~{data['estimated_price']}g | "
            f"last sold {data['last_sold_price']}g via {data['last_sold_source']} | "
            f"latest {data['latest_kind']} {data['latest_price_seen']}g via {data['latest_source']} | "
            f"samples {data['sample_count']} (bm {data['bm_samples']}, #/signal {data['signal_samples']})."
        )
    return "Pricing system returned an unexpected response."


__all__ = [
    "PriceLookupResult",
    "PriceStatus",
    "build_price_response_text",
    "configure_logging",
    "perform_price_lookup",
    "read_timeout_env",
]
