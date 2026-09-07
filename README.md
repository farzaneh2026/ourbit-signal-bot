# Otis CopyTrader → Ourbit Futures v2

A separate project from the existing Toobit bot.

## What was fixed in v2
- Uses the official Ourbit V1 contract endpoints confirmed by the official Postman collection.
- Reads contract metadata before sizing so `contractSize`, minimum volume, volume step, minimum notional and maximum leverage can be respected when those fields are returned by Ourbit.
- Market Entry 1 + Limit Entry 2.
- LONG and SHORT.
- Signal leverage, capped by the contract's reported maximum leverage.
- Protective SL is attached to the opening market order. TP is deliberately NOT attached to the opening order because that could close the whole position instead of doing partial TP.
- TP1/TP2/TP3 are managed as partial market closes using the live remaining position size.
- After TP1, the bot attempts to move the existing exchange stop order to Entry (break-even). If the stop order cannot be found, it logs a warning and does not pretend the move succeeded.
- State is persisted in `otis_state.json`.
- Starts with `DRY_RUN=true`.

## Important safety behavior
Do not switch `DRY_RUN=false` until the Railway logs show that Telegram parsing, Ourbit public contract/ticker calls and private API authentication all work correctly.

The official Ourbit V1 collection confirms the futures endpoints for contract detail, assets, positions, open orders, leverage, order submission, plan orders and stop orders. citeturn7view0turn8view0turn9view0

## Required Railway Variables
- `TG_API_ID`
- `TG_API_HASH`
- `TG_SESSION`
- `TG_SOURCE=otis_ai_bot`
- `OURBIT_API_KEY`
- `OURBIT_API_SECRET`

Recommended first test:
- `DRY_RUN=true`
- `MAX_MARGIN_PCT_PER_ENTRY=0.06`
- `DEFAULT_LEVERAGE=10`
- `POSITION_MODE=2`

Never put API Secret or Telegram session in the source code or ZIP.
