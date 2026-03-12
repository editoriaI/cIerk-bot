# Highrise Bot

## Command

- `!bot`: Summon bot to your current position and facing direction.
- `!unbox`: Start interactive room setup (higher-ranked users only).
- `!answer <text>`: Answer the active unboxing question.
- `!unbox status`: View saved unboxing profile.
- Natural price queries:
  - `how much is Color Mood?`
  - `#ColorMood`
  - `!price color mood`

The summon confirmation is whispered to the user with exact coordinates and facing.

## Setup

```powershell
cd C:\Users\Brian Ware\highrise-bot
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` with:

- `HIGHRISE_ROOM_ID`
- `HIGHRISE_API_TOKEN`
- `HIGHRISE_UNBOX_ADMINS` (comma-separated usernames allowed to run `!unbox`)
- `PRICING_API_BASE` (default `https://webapi.highrise.game`)
- `PRICING_BLACKMARKET_PATHS` (blackmarket-style endpoints; values are reduced by 30%)
- `PRICING_SIGNAL_PATHS` (buy/sell/offer/sold post feeds)
- `HIGHRISE_WEBAPI_AGENT` (optional User-Agent override to mimic Highrise clients)
- `HIGHRISE_WEBAPI_LANG` (optional Accept-Language override for WebAPI calls)
- `DISCORD_BOT_TOKEN`

## Run

```powershell
cd C:\Users\Brian Ware\highrise-bot
.\.venv\Scripts\python src\bot.py
```

## Run Discord Bot

```powershell
cd C:\Users\Brian Ware\highrise-bot
.\.venv\Scripts\python src\discord_bot.py
```

Discord slash setup:
- `/unbox` (requires `Manage Server` or `Administrator`) opens interactive setup modal.
- `/unbox_status` shows saved setup profile for that server.

## Auto Restart (Dev)

Use one command to run both bots with auto-restart after code or `.env` changes:

```powershell
cd C:\Users\Brian Ware\highrise-bot
.\start-dev.ps1
```

## PR Workflow

Create a branch and push it for review:

```powershell
cd C:\Users\Brian Ware\cIerk-bot
.\scripts\new-pr.ps1 your-branch-name
```

Then open a Pull Request for the pushed branch on GitHub.
