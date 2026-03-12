import asyncio
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from highrise import BaseBot, __main__
from highrise.models import Position, SessionMetadata, User
from bot_common import (
    build_price_response_text,
    configure_logging,
    perform_price_lookup,
    read_timeout_env,
)
from pricing_engine import PriceEngine, parse_item_query
from shared_energy import (
    HELP_ALIASES,
    HELP_OVERVIEW_LINES,
    HELP_SECTIONS,
    SUMMON_WHISPER_TEMPLATE,
    UNBOXING_QUESTIONS,
)
from unboxing_store import get_highrise_config, save_highrise_config


configure_logging("clerk")
logger = logging.getLogger(__name__)


class Bot(BaseBot):
    def __init__(self) -> None:
        super().__init__()
        self.bot_user_id: Optional[str] = None
        self.room_id: str = os.getenv("HIGHRISE_ROOM_ID", "")
        self.unbox_sessions: dict[str, dict[str, object]] = {}
        admins = os.getenv("HIGHRISE_UNBOX_ADMINS", "")
        self.unbox_admins = {name.strip().lower() for name in admins.split(",") if name.strip()}
        self.pricing = PriceEngine()
        self.price_timeout = read_timeout_env("PRICE_LOOKUP_TIMEOUT", 6.0)

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        self.bot_user_id = session_metadata.user_id
        logger.info(
            f"Connected as {session_metadata.user_id} "
            f"in room {session_metadata.room_info.room_name}"
        )

    async def on_chat(self, user: User, message: str) -> None:
        try:
            raw = message.strip()
            command = raw.lower()
            logger.info("chat user=%s id=%s msg=%s", user.username, user.id, message)

            if command == "!bot":
                await self._summon_to_user(user)
                return

            if command == "!unbox":
                await self._start_unboxing(user)
                return

            if command == "!unbox status":
                await self._unbox_status(user)
                return

            if command == "!help" or command.startswith("!help "):
                await self._handle_help(user, raw)
                return

            if command.startswith("!answer "):
                answer = raw[len("!answer ") :].strip()
                await self._handle_unbox_answer(user, answer)
                return

            await self._maybe_handle_price_inquiry(user, raw)
        except Exception as exc:
            logger.exception("on_chat failed user=%s id=%s msg=%s", user.username, user.id, message)
            await self._safe_whisper(
                user.id,
                f"Sorry, I hit an error while handling that: {type(exc).__name__}: {exc}",
            )

    async def _safe_whisper(self, user_id: str, text: str) -> None:
        try:
            await self.highrise.send_whisper(user_id, text)
        except Exception:
            logger.exception("failed to whisper user=%s", user_id)

    async def _handle_help(self, user: User, raw_message: str) -> None:
        query = raw_message[len("!help") :].strip().lower()
        if not query:
            await self._send_help_lines(user.id, HELP_OVERVIEW_LINES)
            return

        section = HELP_ALIASES.get(query, query)
        if section in HELP_SECTIONS:
            await self._send_help_lines(user.id, HELP_SECTIONS[section])
            return

        command_key = query if query.startswith("!") else f"!{query}"
        for lines in HELP_SECTIONS.values():
            matching = [line for line in lines if command_key in line.lower()]
            if matching:
                await self._send_help_lines(
                    user.id,
                    [f"Matches for {command_key}:", *matching],
                )
                return

        await self.highrise.send_whisper(
            user.id,
            "No help entry found. Try !help or !help general.",
        )

    async def _send_help_lines(self, user_id: str, lines: list[str]) -> None:
        for line in lines:
            await self.highrise.send_whisper(user_id, line)

    async def _start_unboxing(self, user: User) -> None:
        if self.unbox_admins and user.username.lower() not in self.unbox_admins:
            await self.highrise.send_whisper(
                user.id, "Only a higher-ranked setup user can run !unbox."
            )
            return

        self.unbox_sessions[user.id] = {"step": 0, "answers": {}}
        await self.highrise.send_whisper(
            user.id,
            "Unboxing started. Reply with !answer <text>.\n"
            f"Q1: {UNBOXING_QUESTIONS[0][1]}",
        )

    async def _unbox_status(self, user: User) -> None:
        if not self.room_id:
            await self.highrise.send_whisper(user.id, "Room ID is not configured.")
            return
        config = get_highrise_config(self.room_id)
        if not config:
            await self.highrise.send_whisper(
                user.id, "This room has not been unboxed yet. Use !unbox."
            )
            return
        answers = config.get("answers", {})
        await self.highrise.send_whisper(
            user.id,
            "Current unboxing profile:\n"
            f"mode={answers.get('primary_mode', 'n/a')}, "
            f"moderation={answers.get('moderation_style', 'n/a')}, "
            f"engagement={answers.get('engagement_style', 'n/a')}",
        )

    async def _handle_unbox_answer(self, user: User, answer: str) -> None:
        session = self.unbox_sessions.get(user.id)
        if not session:
            await self.highrise.send_whisper(
                user.id, "No active unboxing session. Use !unbox first."
            )
            return
        if not answer:
            await self.highrise.send_whisper(user.id, "Please provide a non-empty answer.")
            return

        step = int(session["step"])
        key = UNBOXING_QUESTIONS[step][0]
        answers = dict(session["answers"])
        answers[key] = answer
        step += 1

        if step < len(UNBOXING_QUESTIONS):
            session["step"] = step
            session["answers"] = answers
            self.unbox_sessions[user.id] = session
            await self.highrise.send_whisper(
                user.id, f"Saved. Q{step + 1}: {UNBOXING_QUESTIONS[step][1]}"
            )
            return

        if not self.room_id:
            await self.highrise.send_whisper(
                user.id, "Cannot persist unboxing: HIGHRISE_ROOM_ID missing."
            )
            self.unbox_sessions.pop(user.id, None)
            return

        save_highrise_config(self.room_id, user.username, answers)
        self.unbox_sessions.pop(user.id, None)
        await self.highrise.send_whisper(
            user.id,
            "Unboxing complete. Victor/Clerk profile saved for this room.",
        )

    async def _summon_to_user(self, user: User) -> None:
        room_users = (await self.highrise.get_room_users()).content
        target_pos: Optional[Position] = None

        for room_user, pos in room_users:
            if room_user.id == user.id:
                target_pos = pos
                break

        if target_pos is None:
            await self.highrise.send_whisper(
                user.id, "Could not find your current position in this room."
            )
            return

        await self._move_bot_to_position(target_pos)
        await self.highrise.send_whisper(
            user.id,
            SUMMON_WHISPER_TEMPLATE.format(
                x=target_pos.x, y=target_pos.y, z=target_pos.z, facing=target_pos.facing
            ),
        )

    async def _move_bot_to_position(self, target: Position) -> None:
        if not self.bot_user_id:
            return
        await self.highrise.teleport(
            self.bot_user_id,
            Position(target.x, target.y, target.z, facing=target.facing),
        )

    async def _maybe_handle_price_inquiry(self, user: User, message: str) -> None:
        # Ignore command replies and internal setup messages.
        lower = message.strip().lower()
        if lower.startswith("!") and not lower.startswith("!price "):
            return

        item = parse_item_query(message)
        if not item:
            return

        result = await perform_price_lookup(self.pricing, item, self.price_timeout, logger)
        message = build_price_response_text(result, item, self.price_timeout)
        if message:
            await self._safe_whisper(user.id, message)


if __name__ == "__main__":
    load_dotenv()

    room_id = os.getenv("HIGHRISE_ROOM_ID")
    api_token = os.getenv("HIGHRISE_API_TOKEN")

    if not room_id or not api_token:
        raise RuntimeError(
            "Missing HIGHRISE_ROOM_ID or HIGHRISE_API_TOKEN in environment/.env."
        )

    definition = __main__.BotDefinition(bot=Bot(), room_id=room_id, api_token=api_token)
    __main__.arun(__main__.main([definition]))
