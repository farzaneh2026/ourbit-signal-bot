import asyncio
import json
import logging
import os
import re
from pathlib import Path
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from parser import parse_signal, Signal
from ourbit import OurbitClient, OurbitError, _find_records, _as_float
from config import *

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger('otis-copytrader')

seen = set()
client = TelegramClient(StringSession(TG_SESSION), TG_API_ID, TG_API_HASH)
exchange = OurbitClient()
state_path = Path(STATE_FILE)
managed = {}


def load_state():
    global managed
    try:
        if state_path.exists():
            managed = json.loads(state_path.read_text(encoding='utf-8'))
    except Exception:
        log.exception('Could not load state; starting clean')
        managed = {}


def save_state():
    try:
        state_path.write_text(json.dumps(managed, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        log.exception('Could not save state')


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
        a = records[0]
        for key in ('availableBalance', 'available', 'available_balance', 'balance', 'equity'):
            v = _as_float(a.get(key), 0)
            if v > 0:
                return v
    # fallback to assets endpoint
    data = exchange.assets()
    records = _find_records(data)
    for a in records:
        cur = str(a.get('currency', a.get('asset', ''))).upper()
        if cur == 'USDT':
            for key in ('availableBalance', 'available', 'available_balance', 'balance', 'equity'):
                v = _as_float(a.get(key), 0)
                if v > 0:
                    return v
    raise OurbitError('Could not read USDT futures balance from Ourbit response')


def validate_levels(sig: Signal):
    if sig.stop_loss is None or not sig.targets:
        raise ValueError('Signal must contain SL and at least one target')
    targets = [x for x in sig.targets if x is not None]
    if sig.direction == 'LONG':
        if sig.stop_loss >= min(targets):
            raise ValueError('Invalid LONG SL/TP geometry')
    else:
        if sig.stop_loss <= max(targets):
            raise ValueError('Invalid SHORT SL/TP geometry')


async def notify(text):
    if TG_NOTIFY_CHAT_ID:
        try:
            await client.send_message(int(TG_NOTIFY_CHAT_ID), text)
        except Exception:
            log.exception('Notification failed')


def parse_signal_update(text):
    """Detect simple Otis leverage-only follow-ups, e.g. 'اهرم 10 وارد بشید'."""
    m = re.search(r'(?:LEVERAGE|اهرم)\s*[:：]?\s*(\d+)\s*[xX×]?', text or '', re.I)
    if not m:
        return None
    return int(m.group(1))


def current_price(symbol):
    ticker = exchange.ticker(symbol)
    raw = ticker.get('data', ticker) if isinstance(ticker, dict) else ticker
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    price = _as_float(extract_value(raw, 'lastPrice', 'last', 'price', 'fairPrice', default=0))
    if price <= 0:
        raise OurbitError(f'Cannot read live price for {symbol}')
    return price


def position_records(symbol):
    data = exchange.positions(symbol)
    return _find_records(data)


def live_position(symbol, direction):
    records = position_records(symbol)
    want = 1 if direction == 'LONG' else 3
    for p in records:
        ps = str(p.get('symbol', '')).upper()
        if ps and ps != symbol.upper():
            continue
        vol = _as_float(extract_value(p, 'holdVol', 'vol', 'quantity', 'positionVol', default=0))
        ptype = p.get('positionType', p.get('type'))
        if vol > 0 and (ptype is None or int(float(ptype)) == want):
            return p
    return None


def stop_order_id(symbol):
    try:
        data = exchange.stop_orders(symbol)
        for o in _find_records(data):
            oid = extract_value(o, 'orderId', 'id', 'stopPlanOrderId', default=None)
            if oid is None:
                continue
            osym = str(o.get('symbol', symbol)).upper()
            if osym == symbol.upper():
                return oid
    except Exception:
        log.exception('Could not inspect stop orders for %s', symbol)
    return None


def close_side(direction):
    return 4 if direction == 'LONG' else 2


def open_side(direction):
    return 1 if direction == 'LONG' else 3


def target_reached(direction, price, target):
    return price >= target if direction == 'LONG' else price <= target


def calc_volume(price, leverage, equity, contract):
    margin = equity * MAX_MARGIN_PCT_PER_ENTRY
    qty, notional, c = exchange.size_from_margin(price, leverage, margin, contract)
    if notional <= 0:
        raise OurbitError('Calculated notional is invalid')
    return qty, notional, c


async def execute(sig: Signal):
    validate_levels(sig)
    lev = sig.leverage or DEFAULT_LEVERAGE
    if lev <= 0:
        raise ValueError(f'Invalid leverage: {lev}')

    # Normalize symbol format expected by Ourbit V1.
    sig.symbol = sig.symbol.upper().replace('-', '_').replace('/', '_')
    contract = exchange.contract_for(sig.symbol)
    meta = exchange.normalize_contract(contract)
    lev = min(lev, meta['max_leverage'])
    equity = balance_usdt() if not DRY_RUN else None

    log.info('SIGNAL %s %s lev=%sx entries=%s SL=%s TP=%s', sig.direction, sig.symbol, lev, sig.entries, sig.stop_loss, sig.targets)
    await notify(f'📡 Otis signal\n{sig.direction} {sig.symbol} | {lev}x\nSL {sig.stop_loss}\nTP {sig.targets}')

    if DRY_RUN:
        # Public contract + ticker checks are useful even in dry-run, but no private trade.
        live = current_price(sig.symbol)
        margin = (balance_usdt() * MAX_MARGIN_PCT_PER_ENTRY) if OURBIT_API_KEY and OURBIT_API_SECRET else None
        if margin:
            qty, notional, _ = calc_volume(live, lev, equity=balance_usdt(), contract=contract)
            log.info('DRY RUN sizing %s: live=%s qty=%s notional=%s max_margin=%s', sig.symbol, live, qty, notional, margin)
        else:
            log.info('DRY RUN public check: %s live=%s contract=%s', sig.symbol, live, meta)
        return

    # Ensure the leverage is set before opening the position.
    try:
        exchange.change_leverage(sig.symbol, lev)
    except Exception as e:
        log.warning('Leverage change failed/was already set: %s', e)

    for idx in range(min(MAX_ENTRIES, len(sig.entries))):
        price = sig.entries[idx]
        etype = sig.entry_types[idx] if idx < len(sig.entry_types) else 'limit'
        if idx == 0 and etype == 'market':
            price_for_size = current_price(sig.symbol)
            qty, notional, _ = calc_volume(price_for_size, lev, equity, contract)
            # Put the protective SL on the opening order. Do NOT attach TP1 here,
            # otherwise TP1 could close the entire position instead of 30%.
            res = exchange.submit(sig.symbol, open_side(sig.direction), qty, lev, 5,
                                  price=0, stop_loss=sig.stop_loss)
            log.info('MARKET ENTRY sent %s qty=%s notional=%s response=%s', sig.symbol, qty, notional, res)
            entry_price = price_for_size
        elif price is not None:
            qty, notional, _ = calc_volume(price, lev, equity, contract)
            res = exchange.submit(sig.symbol, open_side(sig.direction), qty, lev, 1,
                                  price=price)
            log.info('LIMIT ENTRY %s price=%s qty=%s notional=%s response=%s', sig.symbol, price, qty, notional, res)
            entry_price = price
        else:
            continue

        key = f'{sig.symbol}:{sig.direction}:{sig.source_message_id or 0}'
        managed[key] = {
            'symbol': sig.symbol,
            'direction': sig.direction,
            'leverage': lev,
            'entry_price': entry_price,
            'stop_loss': sig.stop_loss,
            'targets': sig.targets[:3],
            'tp_done': [False, False, False],
            'be_done': False,
            'created_message_id': sig.source_message_id,
        }
        save_state()

    await notify(f'✅ Otis order processing started: {sig.symbol} {sig.direction} | {lev}x')


async def manage_trade(key, trade):
    symbol = trade['symbol']
    direction = trade['direction']
    targets = trade.get('targets', [])[:3]
    price = current_price(symbol)
    pos = live_position(symbol, direction)
    if not pos:
        # Position may simply be waiting for Entry 2. Keep state for now.
        return
    hold = int(_as_float(extract_value(pos, 'holdVol', 'vol', 'quantity', 'positionVol', default=0)))
    if hold <= 0:
        return

    # Capture the first observed live position as the base quantity for the TP split.
    if not trade.get('initial_hold'):
        trade['initial_hold'] = hold
        save_state()

    # Use exchange stop order if available. If TP1 is hit, move the SL to entry.
    for i, target in enumerate(targets):
        if trade['tp_done'][i] or not target_reached(direction, price, target):
            continue
        remaining = int(_as_float(extract_value(pos, 'holdVol', 'vol', 'quantity', 'positionVol', default=0)))
        if remaining <= 0:
            trade['tp_done'][i] = True
            continue

        # Close TP1/TP2 as percentages of the original observed position; TP3 closes the rest.
        base = int(trade.get('initial_hold') or remaining)
        if i == 0:
            close_qty = max(1, int(round(base * TP1_PCT)))
        elif i == 1:
            close_qty = max(1, int(round(base * TP2_PCT)))
        else:
            close_qty = remaining
        close_qty = min(close_qty, remaining)

        # A partial close is sent as a market close order. This avoids guessing a trigger-order
        # schema for partial quantities while keeping the protective SL on the position.
        res = exchange.submit(symbol, close_side(direction), close_qty, trade['leverage'], 5, price=0)
        log.info('TP%d HIT %s price=%s target=%s close_qty=%s response=%s', i + 1, symbol, price, target, close_qty, res)
        trade['tp_done'][i] = True
        save_state()

        if i == 0 and not trade.get('be_done'):
            sid = stop_order_id(symbol)
            if sid is not None:
                try:
                    exchange.change_stop(sid, sl=trade['entry_price'], tp=0)
                    log.info('TP1 -> break-even: %s stop_order=%s entry=%s', symbol, sid, trade['entry_price'])
                except Exception:
                    log.exception('Failed to move SL to break-even for %s', symbol)
            else:
                log.warning('TP1 hit but no stop order id was found for %s; SL was NOT changed', symbol)
            trade['be_done'] = True
            save_state()

        # Refresh position after each close so the next target uses live remaining volume.
        await asyncio.sleep(0.5)
        pos = live_position(symbol, direction)
        if not pos:
            break


async def manager_loop():
    while True:
        try:
            if not DRY_RUN:
                for key, trade in list(managed.items()):
                    try:
                        await manage_trade(key, trade)
                    except Exception:
                        log.exception('Position manager failed for %s', key)
        except Exception:
            log.exception('Position manager loop error')
        await asyncio.sleep(max(1, POLL_SECONDS))


@client.on(events.NewMessage(chats=int(TG_SOURCE)))
async def on_message(event):
    text = event.raw_text or ''
    sig = parse_signal(text, event.id)
    if not sig:
        lev = parse_signal_update(text)
        if lev:
            log.info('Otis leverage update detected: %sx | message=%s', lev, event.id)
        return
    key = (sig.symbol, sig.direction, event.id)
    if key in seen:
        return
    seen.add(key)
    try:
        await execute(sig)
    except Exception as e:
        log.exception('Signal execution failed')
        await notify(f'❌ Otis execution failed: {sig.symbol} {sig.direction}\n{e}')


async def main():
    load_state()
    if not TG_API_ID or not TG_API_HASH:
        raise SystemExit('Set TG_API_ID and TG_API_HASH in Railway variables.')
    if not TG_SESSION:
        raise SystemExit('TG_SESSION is not set. Generate a Telethon StringSession and add it to Railway variables.')
    log.info('Otis CopyTrader v2 starting | source=%s | DRY_RUN=%s | Ourbit=%s', TG_SOURCE, DRY_RUN, OURBIT_API_BASE)
    try:
        health = exchange.health_check()
        log.info('Ourbit V1 API health: %s', health)
        if not health.get('api'):
            log.warning('Ourbit DNS/API is not reachable yet; Telegram will keep running safely.')
            log.info('Ourbit DNS diagnostic (no base switching): %s', exchange.diagnostic_dns())
    except Exception as e:
        log.warning('Ourbit startup diagnostic failed (non-fatal): %s', e)
    await client.start(bot_token=None)
    me = await client.get_me()
    log.info('Telegram account connected: %s', getattr(me, 'username', None) or getattr(me, 'id', None))
    manager = asyncio.create_task(manager_loop())
    try:
        await client.run_until_disconnected()
    finally:
        manager.cancel()


if __name__ == '__main__':
    asyncio.run(main())
