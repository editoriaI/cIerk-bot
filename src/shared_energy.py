ENERGY_TAG = "Clerk Core"

SUMMON_WHISPER_TEMPLATE = (
    "[Clerk Core] Summoned. Position synced to x={x:.2f}, y={y:.2f}, z={z:.2f}, facing={facing}."
)

DISCORD_READY_MESSAGE = "Clerk Discord is online and synced with Clerk Core energy."

UNBOXING_QUESTIONS = [
    (
        "primary_mode",
        "What should Victor prioritize in this guild? (trading, community, support, events)",
    ),
    (
        "moderation_style",
        "How strict should moderation be? (chill, balanced, strict)",
    ),
    (
        "engagement_style",
        "How should it engage users? (whisper-first, channel-first, hybrid)",
    ),
]

HELP_OVERVIEW_LINES = [
    "Victor is your trade middleman. Use !help [section] or !help [command].",
    "Available sections: market, storefront, outfit, subscriptions, promos, wallet, host.",
]

HELP_SECTIONS = {
    "market": [
        "📈 Market:",
        "how much is [item]? | #ItemName | !price [item]",
        "!wl | !wl [item] | !wl remove [item] | !wl clear | !wl price | !wl @user",
        "!ideas | !color | !report",
    ],
    "storefront": [
        "🛒 Storefront:",
        "!sf | !sf sell | !sf tag",
    ],
    "outfit": [
        "👗 Outfit:",
        "!fit | !fit @user",
    ],
    "subscriptions": [
        "🔔 Subscriptions:",
        "!sub | !sub ideas | !unsub",
    ],
    "promos": [
        "🎁 Promos:",
        "!giveaway | !giveaway pick",
        "!promo | !promo @name | !toppromos | !prolb",
    ],
    "wallet": [
        "💰 Wallet:",
        "!bal | !cashout",
    ],
    "host": [
        "🧰 Host Tools:",
        "!bot | !unbox | !unbox status | !answer [text]",
    ],
}

HELP_ALIASES = {
    "wishlist": "market",
    "wl": "market",
    "price": "market",
    "sf": "storefront",
    "fit": "outfit",
    "sub": "subscriptions",
    "balance": "wallet",
    "economy": "wallet",
    "trading": "market",
}
