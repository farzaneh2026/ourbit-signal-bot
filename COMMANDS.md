# Toobit → Ourbit CopyTrader

This bot has no Otis signal source.

It automatically watches `TOOBIT_SOURCE` and copies only confirmed Toobit trade messages.

## Copied trade

- Direction: BUY/LONG or SELL/SHORT
- Entry: Toobit's confirmed entry
- TP: one full TP
- SL: one full SL
- No TP1/TP2/TP3
- No break-even

## Testing

Keep `DRY_RUN=true` first. A valid Toobit confirmation should produce a log similar to:

`DRY RUN OK | source=TOOBIT | BTC_USDT LONG | entry=... TP=... SL=...`
