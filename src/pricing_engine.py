import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


PRICE_RE = re.compile(r"(?<!\d)(\d{1,7})(?:\s*(?:g|gold))?(?!\d)", re.IGNORECASE)
HASH_ITEM_RE = re.compile(r"#([A-Za-z0-9_]+)")
HOW_MUCH_RE = re.compile(r"how much(?:\s+is|'s)?\s+(.+?)\??$", re.IGNORECASE)


def normalize_item_name(value: str) -> str:
    value = re.sub(r"[^a-z0-9 ]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", value)


def hashtag_to_item(tag: str) -> str:
    # Convert ColorMood -> color mood, color_mood -> color mood
    token = re.sub(r"_+", " ", tag)
    token = re.sub(r"([a-z])([A-Z])", r"\1 \2", token)
    return normalize_item_name(token)


def parse_item_query(message: str) -> str | None:
    text = message.strip()
    lower = text.lower()
    if lower.startswith("!price "):
        return normalize_item_name(text[len("!price ") :])

    match = HOW_MUCH_RE.search(text)
    if match:
        return normalize_item_name(match.group(1))

    hash_match = HASH_ITEM_RE.search(text)
    if hash_match:
        return hashtag_to_item(hash_match.group(1))

    return None


def _json_get(url: str, timeout: int = 8) -> Any:
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        raw = res.read().decode("utf-8", errors="replace")
        return json.loads(raw)


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _text_blob(entry: dict[str, Any]) -> str:
    fields = []
    for key in ("caption", "content", "body", "text", "description", "title", "message"):
        v = entry.get(key)
        if isinstance(v, str) and v.strip():
            fields.append(v.strip())
    return " | ".join(fields)


def _timestamp(entry: dict[str, Any]) -> str:
    for key in ("created_at", "createdAt", "updated_at", "timestamp", "time"):
        v = entry.get(key)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def _to_epoch(value: str) -> float:
    if not value:
        return 0.0
    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value).timestamp()
    except Exception:
        return 0.0


def _signal_kind(text: str) -> str:
    lower = text.lower()
    if "last sold" in lower or " sold " in f" {lower} ":
        return "sold"
    if "#selling" in lower or "selling" in lower:
        return "selling"
    if "#buying" in lower or "buying" in lower:
        return "buying"
    if "offer" in lower:
        return "offer"
    return "unknown"


@dataclass
class PriceHit:
    price: float
    source: str
    weight: float
    timestamp: float
    signal_kind: str
    market_type: str


class PriceEngine:
    def __init__(self) -> None:
        self.base_url = os.getenv("PRICING_API_BASE", "http://localhost:4000/highrise").rstrip("/")
        self.blackmarket_paths = [
            p.strip()
            for p in os.getenv(
                "PRICING_BLACKMARKET_PATHS",
                "/market/blackmarket,/posts,/feed,/storefront/listings",
            ).split(",")
            if p.strip()
        ]
        self.signal_paths = [
            p.strip()
            for p in os.getenv(
                "PRICING_SIGNAL_PATHS",
                "/posts,/feed,/activities",
            ).split(",")
            if p.strip()
        ]

    def lookup(self, item_name: str) -> dict[str, Any]:
        normalized = normalize_item_name(item_name)
        compact = normalized.replace(" ", "")
        hash_variant = f"#{compact}"

        hits: list[PriceHit] = []
        hits.extend(self._collect_from_paths(normalized, hash_variant, self.blackmarket_paths, blackmarket=True))
        hits.extend(self._collect_from_paths(normalized, hash_variant, self.signal_paths, blackmarket=False))

        if not hits:
            return {
                "item": normalized,
                "found": False,
                "message": "No recent price signals found.",
            }

        weighted_sum = sum(h.price * h.weight for h in hits)
        weight_total = sum(h.weight for h in hits) or 1.0
        estimate = weighted_sum / weight_total
        latest = max(hits, key=lambda h: h.timestamp if h.timestamp else 0.0)
        sold_hits = [h for h in hits if h.signal_kind == "sold"]
        latest_sold = max(sold_hits, key=lambda h: h.timestamp if h.timestamp else 0.0) if sold_hits else latest

        bm_hits = sum(1 for h in hits if h.market_type == "bm")
        signal_hits = len(hits) - bm_hits

        return {
            "item": normalized,
            "found": True,
            "estimated_price": round(estimate, 2),
            "latest_price_seen": round(latest.price, 2),
            "latest_source": latest.source,
            "latest_kind": latest.signal_kind,
            "last_sold_price": round(latest_sold.price, 2),
            "last_sold_source": latest_sold.source,
            "sample_count": len(hits),
            "bm_samples": bm_hits,
            "signal_samples": signal_hits,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def _collect_from_paths(
        self,
        item_name: str,
        hash_variant: str,
        paths: list[str],
        blackmarket: bool,
    ) -> list[PriceHit]:
        results: list[PriceHit] = []
        for path in paths:
            for url in self._candidate_urls(path):
                try:
                    payload = _json_get(url)
                except Exception:
                    continue
                for node in _walk(payload):
                    text_blob = _text_blob(node)
                    if not text_blob:
                        continue
                    normalized_text = normalize_item_name(text_blob)
                    if item_name not in normalized_text and hash_variant.lower() not in text_blob.lower():
                        continue

                    prices = [float(m.group(1)) for m in PRICE_RE.finditer(text_blob)]
                    if not prices:
                        continue
                    picked = prices[-1]
                    weight = self._weight_for_text(text_blob, blackmarket=blackmarket)
                    if blackmarket:
                        picked = picked * 0.70
                    results.append(
                        PriceHit(
                            price=picked,
                            source=f"{path}{' (bm-30%)' if blackmarket else ' (#/signal)'}",
                            weight=weight,
                            timestamp=_to_epoch(_timestamp(node)),
                            signal_kind=_signal_kind(text_blob),
                            market_type="bm" if blackmarket else "signal",
                        )
                    )
        return results

    def _candidate_urls(self, path: str) -> list[str]:
        path = path if path.startswith("/") else f"/{path}"
        query = urllib.parse.urlencode({"limit": 100})
        return [f"{self.base_url}{path}?{query}", f"{self.base_url}{path}"]

    @staticmethod
    def _weight_for_text(text: str, blackmarket: bool) -> float:
        signal = _signal_kind(text)
        if signal == "sold":
            base = 1.6
        elif signal == "selling":
            base = 1.2
        elif signal == "buying":
            base = 1.0
        elif signal == "offer":
            base = 0.9
        else:
            base = 0.7
        if blackmarket:
            base += 0.2
        return base
