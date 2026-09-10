# Otis CopyTrader → Ourbit Futures v2

Separate Telegram-to-Ourbit futures copy trader.

## Main behavior
- Telethon `StringSession` from Railway `TG_SESSION` (no phone prompt on Railway).
- Parses LONG/SHORT signals, symbol, leverage, up to 2 entries, SL and up to 3 targets.
- Uses Ourbit V1 contract metadata before sizing.
- Market Entry 1 + Limit Entry 2 when supplied by the signal.
- One persistent trade state is used for both entries; Entry 2 no longer overwrites Entry 1 state.
- Protective SL is attached to Market Entry 1.
- TP1/TP2/TP3 are managed as partial market closes from live remaining position size.
- After TP1, the bot attempts to move the existing exchange stop to entry/break-even.
- Channel follow-up commands are supported for:
  - percentage partial close (`30% close`, `30 درصد ببند`)
  - half close (`نصف پوزیشن`)
  - full close / exit
  - break-even / risk-free (`ریسک فری`, `break even`, `SL to entry`)
  - explicit SL move (`SL 123.45` / `SL to 123.45`)
- A follow-up command without a symbol is executed only when exactly one active managed trade is unambiguous.
- State is persisted in `otis_state.json`.
- `DRY_RUN=true` is the safe default.

## Important
The current default futures V1 base remains `https://futures.ourbit.com` because that is the V1 contract base supported by the project. Do not change it to the generic `api.ourbit.com` unless Ourbit documents a compatible V1 contract replacement.

Do not switch `DRY_RUN=false` until Telegram parsing, public Ourbit endpoints, and private authentication have been verified.

## Security
Never commit `.env`, Telegram StringSession files/values, API keys, API secrets, or `otis_state.json`.
