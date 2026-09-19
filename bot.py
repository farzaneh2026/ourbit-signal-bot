import asyncio
import json
import logging
from pathlib import Path

from telethon import TelegramClient, events
from telethon.sessions import StringSession

from parser import parse_toobit_signal, Signal
from ourbit import OurbitClient, OurbitError, _find_records, _as_float
from config import *

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
log = logging.getLogger('toobit-copytrader')

seen = set()
client = TelegramClient(StringSession(TG_SESSION), TG_API_ID, TG_API_HASH)
exchange = OurbitClient()
state_path = Path(STATE_FILE)


def load_state():
    global seen
    try:
        if state_path.exists():
            data = json.loads(state_path.read_text(encoding='utf-8'))
            seen = set(data.get('seen', []))
    except Exception:
        log.exception('Could not load copy state; starting clean')


def save_state():
    try:
        state_path.write_text(
            json.dumps({'seen': list(seen)[-500:]}, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
    except Exception:
        log.exception('Could not save copy state')


def extract_value(obj, *keys, default=None):
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and obj[k] is not None:
                return obj[k]
    return default


def balance_usdt():
    data = exchange.asset_usdt()
    raw = data.get('data', data) if isinstance(data, dict) else data
    records = _find_records(raw)
    if records:
        for key in ('availableBalance', 'available', 'available_balance', 'balance', 'equity'):
            v = _as_float(records[0].get(key), 0)
            if v > 0:
                return v
    data = exchange.assets()
    for a in _find_records(data):
        cur = str(a.get('currency', a.get('asset', ''))).upper()
        if cur == 'USDT':
            for key in ('availableBalance', 'available', 'available_balance', 'balance', 'equity'):
                v = _as_float(a.get(key), 0)
                if v > 0:
                    return v
    raise OurbitError('Could not read USDT futures balance from Ourbit response')


def calc_volume(price, leverage, equity, contract):
    margin = equity * MAX_MARGIN_PCT_PER_ENTRY
    qty, notional, meta = exchange.size_from_margin(price, leverage, margin, contract)
    if notional <= 0:
        raise OurbitError('Calculated notional is invalid')
    return qty, notional, meta


async def notify(message):
    if not TG_NOTIFY_CHAT_ID:
        return
    try:
        await client.send_message(int(TG_NOTIFY_CHAT_ID), message)
    except Exception:
        log.exception('Notification failed')


def validate_signal(sig: Signal):
    if sig.entry is None or sig.stop_loss is None or sig.take_profit is None:
        raise ValueError('Toobit signal is missing Entry, TP or SL')
    if sig.direction == 'LONG' and not (sig.stop_loss < sig.entry < sig.take_profit):
        raise ValueError('Invalid LONG Entry/TP/SL geometry')
    if sig.direction == 'SHORT' and not (sig.take_profit < sig.entry < sig.stop_loss):
        raise ValueError('Invalid SHORT Entry/TP/SL geometry')


def open_side(direction):
    return 1 if direction == 'LONG' else 3


async def execute(sig: Signal):
    validate_signal(sig)
    sig.symbol = sig.symbol.upper().replace('-', '_').replace('/', '_')

    contract = exchange.contract_for(sig.symbol)
    meta = exchange.normalize_contract(contract)
    lev = min(sig.leverage or DEFAULT_LEVERAGE, meta['max_leverage'])

    log.info(
        'TOOBIT COPY | %s %s | entry=%s tp=%s sl=%s lev=%sx | confirmed=%s',
        sig.direction, sig.symbol, sig.entry, sig.take_profit, sig.stop_loss,
        lev, sig.confirmed
    )

    if DRY_RUN:
        log.info(
            'DRY RUN OK | source=TOOBIT | %s %s | entry=%s TP=%s SL=%s | max_leverage=%s',
            sig.symbol, sig.direction, sig.entry, sig.take_profit,
            sig.stop_loss, meta['max_leverage']
        )
        await notify(
            f'🟡 DRY RUN — Toobit → Ourbit\n'
            f'{sig.direction} {sig.symbol}\n'
            f'Entry: {sig.entry}\nTP: {sig.take_profit}\nSL: {sig.stop_loss}\n'
            f'Leverage: {lev}x'
        )
        return

    equity = balance_usdt()
    try:
        exchange.change_leverage(sig.symbol, lev)
    except Exception as e:
        log.warning('Leverage change failed/was already set: %s', e)

    qty, notional, _ = calc_volume(sig.entry, lev, equity, contract)

    # One copied entry + one full TP + one full SL. No TP1/TP2/TP3 and no BE.
    res = exchange.submit(
        sig.symbol,
        open_side(sig.direction),
        qty,
        lev,
        1,  # LIMIT
        price=sig.entry,
        stop_loss=sig.stop_loss,
        take_profit=sig.take_profit,
    )

    log.info(
        'COPIED ORDER SENT | %s %s | qty=%s notional=%s entry=%s TP=%s SL=%s response=%s',
        sig.symbol, sig.direction, qty, notional, sig.entry, sig.take_profit,
        sig.stop_loss, res
    )

    await notify(
        f'🟢 Toobit → Ourbit copied\n'
        f'{sig.direction} {sig.symbol}\n'
        f'Entry: {sig.entry}\nTP (Full): {sig.take_profit}\nSL: {sig.stop_loss}\n'
        f'Qty: {qty} | Leverage: {lev}x'
    )


async def process_message(event, edited=False):
    text = event.raw_text or ''
    log.info(
        'TOOBIT %s | chat_id=%s message=%s text=%r',
        'EDIT' if edited else 'MESSAGE', event.chat_id, event.id, text
    )

    sig = parse_toobit_signal(text, event.id)
    if not sig:
        log.info('Ignored non-confirmed/non-trade Toobit message id=%s', event.id)
        return

    key = f'{event.chat_id}:{event.id}'
    if key in seen:
        log.info('Duplicate Toobit message ignored: %s', key)
        return
    seen.add(key)
    save_state()

    try:
        await execute(sig)
    except Exception as exc:
        log.exception('Toobit copy execution failed')
        await notify(
            f'❌ Toobit → Ourbit copy failed\n'
            f'{sig.direction} {sig.symbol}\n{exc}'
        )


@client.on(events.NewMessage(chats=TOOBIT_SOURCE))
async def on_message(event):
    await process_message(event, edited=False)


@client.on(events.MessageEdited(chats=TOOBIT_SOURCE))
async def on_message_edited(event):
    await process_message(event, edited=True)


async def main():
    load_state()

    if not TG_API_ID or not TG_API_HASH:
        raise SystemExit('Set TG_API_ID and TG_API_HASH in Rawly variables.')
    if not TG_SESSION:
        raise SystemExit('TG_SESSION is not set.')
    if not TOOBIT_SOURCE:
        raise SystemExit(
            'TOOBIT_SOURCE is not set. Set it to the Telegram chat/channel where the Toobit bot sends confirmed trade messages.'
        )

    log.info(
        'Toobit → Ourbit CopyTrader starting | source=%s | DRY_RUN=%s | Ourbit=%s',
        TOOBIT_SOURCE, DRY_RUN, OURBIT_API_BASE
    )

    await client.start(bot_token=None)
    me = await client.get_me()
    log.info('Telegram account connected: %s', getattr(me, 'username', None) or getattr(me, 'id', None))
    log.info('COPY MODE: confirmed Toobit trades only | 1 Entry + 1 full TP + 1 SL')
    await client.run_until_disconnected()


if __name__ == '__main__':
    asyncio.run(main())
