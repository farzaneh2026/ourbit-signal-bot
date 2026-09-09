# Channel follow-up commands

The bot listens to the configured Telegram source and can act on management messages after a signal.

## Supported

- Partial close: `30% close`, `30 درصد ببند`, `30 درصد سیو سود`
- Half close: `نصف پوزیشن`, `50% position`
- Full close: `close all`, `full close`, `بستن کامل`, `خروج کامل`
- Break-even / risk-free: `risk free`, `break even`, `SL to entry`, `ریسک فری`
- Explicit SL move: `SL to 123.45`, `SL 123.45`, `حد ضرر 123.45`

A management message without a symbol is only applied when exactly one active managed trade is unambiguous. If there are multiple active trades, the command is logged and ignored rather than guessing.

## Safety

Keep `DRY_RUN=true` while testing. Do not commit credentials, `.env`, Telegram sessions, API secrets, or `otis_state.json`.
