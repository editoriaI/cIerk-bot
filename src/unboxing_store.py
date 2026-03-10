import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_PATH = DATA_DIR / "unboxing_config.json"


def _load() -> dict[str, Any]:
    if not DATA_PATH.exists():
        return {"highrise": {}, "discord": {}}
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def _save(payload: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def save_highrise_config(room_id: str, configured_by: str, answers: dict[str, str]) -> dict[str, Any]:
    payload = _load()
    payload.setdefault("highrise", {})
    payload["highrise"][room_id] = {
        "configured_by": configured_by,
        "answers": answers,
    }
    _save(payload)
    return payload["highrise"][room_id]


def get_highrise_config(room_id: str) -> dict[str, Any] | None:
    payload = _load()
    return payload.get("highrise", {}).get(room_id)


def save_discord_config(guild_id: str, configured_by: str, answers: dict[str, str]) -> dict[str, Any]:
    payload = _load()
    payload.setdefault("discord", {})
    payload["discord"][guild_id] = {
        "configured_by": configured_by,
        "answers": answers,
    }
    _save(payload)
    return payload["discord"][guild_id]


def get_discord_config(guild_id: str) -> dict[str, Any] | None:
    payload = _load()
    return payload.get("discord", {}).get(guild_id)
