# Toobit → Ourbit CopyTrader

This project no longer listens to Otis signals.

It listens to the Telegram chat/channel where the **Toobit AI Trader** sends its confirmed trade messages and copies those trades to **Ourbit Futures**.

## Copy flow

1. Toobit scans and creates a signal.
2. The user confirms the trade in the Toobit bot.
3. Toobit sends its confirmed execution message containing Symbol, Signal, Entry, TP and SL.
4. This copier reads that confirmed message.
5. The same direction, entry, TP and SL are sent to Ourbit.
6. The Ourbit copy uses **one entry + one full TP + one full SL**. No TP1/TP2/TP3 and no break-even logic.

Pending Toobit signals are intentionally ignored. This prevents an unapproved/rejected Toobit signal from opening a position on Ourbit.

## Required Rawly variables

- `TG_API_ID`
- `TG_API_HASH`
- `TG_SESSION`
- `TOOBIT_SOURCE` — Telegram chat ID/channel ID or public username where the Toobit bot posts its confirmed trade messages
- `OURBIT_API_KEY`
- `OURBIT_API_SECRET`

Recommended first test:
- `DRY_RUN=true`
- `MAX_MARGIN_PCT_PER_ENTRY=0.06`
- `DEFAULT_LEVERAGE=10`
- `POSITION_MODE=2`

## Important

- This project is separate from the Toobit trader itself; it only consumes its confirmed Telegram messages.
- No Otis source/channel/parser is used.
- Keep `DRY_RUN=true` until the logs show that the Toobit message is parsed correctly and the Ourbit public/private API tests are successful.
- Never put API secrets or Telegram StringSession values in the ZIP or GitHub.
