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


# ============================================================
# Telegram source
# ============================================================

TOOBIT_SOURCE_NAME = "Toobit AI Trader"
# Prefer the dedicated Toobit source variable. Keep TG_SOURCE as a
# backwards-compatible fallback so the existing deployment does not break.
TOOBIT_SOURCE_ID_RAW = (
    os.getenv("TOOBIT_SOURCE", "").strip()
    or os.getenv("TG_SOURCE", "").strip()
)

if not TOOBIT_SOURCE_ID_RAW:
    raise SystemExit(
        "TOOBIT_SOURCE is not set. "
        "Add TOOBIT_SOURCE to Rawly Environment Variables."
    )

try:
    TG_SOURCE_ID = int(TOOBIT_SOURCE_ID_RAW)
except (TypeError, ValueError):
    raise SystemExit(
        f"TOOBIT_SOURCE must be a numeric Telegram Chat ID. "
        f"Current value: {TOOBIT_SOURCE_ID_RAW!r}"
    )


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("toobit-copytrader")

seen = set()

client = TelegramClient(
    StringSession(TG_SESSION),
    TG_API_ID,
    TG_API_HASH
)

exchange = OurbitClient()

state_path = Path(STATE_FILE)
managed = {}


# ============================================================
# State
# ============================================================

def load_state():
    global managed

    try:
        if state_path.exists():
            managed = json.loads(
                state_path.read_text(
                    encoding="utf-8"
                )
            )
    except Exception:
        log.exception(
            "Could not load state; starting clean"
        )
        managed = {}


def save_state():
    try:
        state_path.write_text(
            json.dumps(
                managed,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )
    except Exception:
        log.exception(
            "Could not save state"
        )


# ============================================================
# Helpers
# ============================================================

def extract_value(obj, *keys, default=None):
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and obj[k] is not None:
                return obj[k]

    return default


def balance_usdt():
    data = exchange.asset_usdt()

    raw = (
        data.get("data", data)
        if isinstance(data, dict)
        else data
    )

    records = _find_records(raw)

    if records:
        a = records[0]

        for key in (
            "availableBalance",
            "available",
            "available_balance",
            "balance",
            "equity"
        ):
            v = _as_float(
                a.get(key),
                0
            )

            if v > 0:
                return v

    data = exchange.assets()

    records = _find_records(data)

    for a in records:
        cur = str(
            a.get(
                "currency",
                a.get(
                    "asset",
                    ""
                )
            )
        ).upper()

        if cur == "USDT":
            for key in (
                "availableBalance",
                "available",
                "available_balance",
                "balance",
                "equity"
            ):
                v = _as_float(
                    a.get(key),
                    0
                )

                if v > 0:
                    return v

    raise OurbitError(
        "Could not read USDT futures balance "
        "from Ourbit response"
    )


def validate_levels(sig: Signal):
    if (
        sig.stop_loss is None
        or not sig.targets
    ):
        raise ValueError(
            "Signal must contain SL and at least one target"
        )

    targets = [
        x
        for x in sig.targets
        if x is not None
    ]

    if sig.direction == "LONG":
        if sig.stop_loss >= min(targets):
            raise ValueError(
                "Invalid LONG SL/TP geometry"
            )

    else:
        if sig.stop_loss <= max(targets):
            raise ValueError(
                "Invalid SHORT SL/TP geometry"
            )


async def notify(text):
    if TG_NOTIFY_CHAT_ID:
        try:
            await client.send_message(
                int(TG_NOTIFY_CHAT_ID),
                text
            )
        except Exception:
            log.exception(
                "Notification failed"
            )


def parse_signal_update(text):
    m = re.search(
        r"(?:LEVERAGE|اهرم)\s*[:：]?\s*(\d+)\s*[xX×]?",
        text or "",
        re.I
    )

    if not m:
        return None

    return int(m.group(1))



# ============================================================
# Toobit confirmation gate
# ============================================================
# IMPORTANT:
# A Telegram inline-button click is delivered to the Toobit bot itself.
# CopyTrader (running as a Telegram user session) cannot directly receive
# that callback.  Therefore this project NEVER executes on the initial
# signal message.  It executes only when Toobit publishes/edits the signal
# with an explicit confirmation marker.
#
# Keep this list deliberately strict: the initial signal may contain
# generic "confirm" instructions or a green emoji, so those are NOT enough.

CONFIRMATION_PATTERNS = (
    r'\bTRADE\s+CONFIRMED\b',
    r'\bSIGNAL\s+CONFIRMED\b',
    r'\bCONFIRMED\s+TRADE\b',
    r'\bCONFIRMED\b',
    r'\bAPPROVED\b',
    r'\bEXECUTED\s+CONFIRMED\b',
    r'تایید\s*شد',
    r'تأیید\s*شد',
    r'معامله\s*تایید(?:\s+و\s+باز)?\s*شد',
    r'معامله\s*تأیید(?:\s+و\s+باز)?\s*شد',
)

def is_confirmed_signal_text(text: str) -> bool:
    """Return True only for an explicit Toobit confirmation marker."""
    if not text:
        return False
    t = _normalize_confirmation_text(text)
    return any(re.search(p, t, re.I) for p in CONFIRMATION_PATTERNS)

def _normalize_confirmation_text(text: str) -> str:
    return (
        text.replace('ي', 'ی')
            .replace('ى', 'ی')
            .replace('ك', 'ک')
            .replace('ة', 'ه')
            .replace('ۀ', 'ه')
            .replace('‌', ' ')
    )

def current_price(symbol):
    ticker = exchange.ticker(
        symbol
    )

    raw = (
        ticker.get("data", ticker)
        if isinstance(ticker, dict)
        else ticker
    )

    if isinstance(raw, list):
        raw = (
            raw[0]
            if raw
            else {}
        )

    price = _as_float(
        extract_value(
            raw,
            "lastPrice",
            "last",
            "price",
            "fairPrice",
            default=0
        )
    )

    if price <= 0:
        raise OurbitError(
            f"Cannot read live price for {symbol}"
        )

    return price


def position_records(symbol):
    data = exchange.positions(
        symbol
    )

    return _find_records(data)


def live_position(symbol, direction):
    records = position_records(
        symbol
    )

    want = (
        1
        if direction == "LONG"
        else 3
    )

    for p in records:
        ps = str(
            p.get(
                "symbol",
                ""
            )
        ).upper()

        if ps and ps != symbol.upper():
            continue

        vol = _as_float(
            extract_value(
                p,
                "holdVol",
                "vol",
                "quantity",
                "positionVol",
                default=0
            )
        )

        ptype = p.get(
            "positionType",
            p.get("type")
        )

        if (
            vol > 0
            and (
                ptype is None
                or int(float(ptype)) == want
            )
        ):
            return p

    return None


def stop_order_id(symbol):
    try:
        data = exchange.stop_orders(
            symbol
        )

        for o in _find_records(data):
            oid = extract_value(
                o,
                "orderId",
                "id",
                "stopPlanOrderId",
                default=None
            )

            if oid is None:
                continue

            osym = str(
                o.get(
                    "symbol",
                    symbol
                )
            ).upper()

            if osym == symbol.upper():
                return oid

    except Exception:
        log.exception(
            "Could not inspect stop orders for %s",
            symbol
        )

    return None


def close_side(direction):
    return (
        4
        if direction == "LONG"
        else 2
    )


def open_side(direction):
    return (
        1
        if direction == "LONG"
        else 3
    )


def target_reached(
    direction,
    price,
    target
):
    return (
        price >= target
        if direction == "LONG"
        else price <= target
    )


def calc_volume(
    price,
    leverage,
    equity,
    contract
):
    margin = (
        equity
        * MAX_MARGIN_PCT_PER_ENTRY
    )

    qty, notional, c = exchange.size_from_margin(
        price,
        leverage,
        margin,
        contract
    )

    if notional <= 0:
        raise OurbitError(
            "Calculated notional is invalid"
        )

    return qty, notional, c


# ============================================================
# Execute signal
# ============================================================

async def execute(sig: Signal):

    validate_levels(sig)

    lev = (
        sig.leverage
        or DEFAULT_LEVERAGE
    )

    if lev <= 0:
        raise ValueError(
            f"Invalid leverage: {lev}"
        )

    sig.symbol = (
        sig.symbol
        .upper()
        .replace("-", "_")
        .replace("/", "_")
    )

    contract = exchange.contract_for(
        sig.symbol
    )

    meta = exchange.normalize_contract(
        contract
    )

    lev = min(
        lev,
        meta["max_leverage"]
    )

    log.info(
        "SIGNAL %s %s lev=%sx entries=%s "
        "SL=%s TP=%s",
        sig.direction,
        sig.symbol,
        lev,
        sig.entries,
        sig.stop_loss,
        sig.targets
    )

    await notify(
        f"📡 Toobit signal\n"
        f"{sig.direction} {sig.symbol} | {lev}x\n"
        f"SL {sig.stop_loss}\n"
        f"TP {sig.targets}"
    )

    # ========================================================
    # OURBIT BALANCE PREFLIGHT
    # ========================================================
    # Ourbit's current API Read permission does not include Asset/Balance
    # reads. Calling /private/account/asset/USDT therefore returns code 701.
    # A confirmed trade must not be blocked by that unsupported preflight.
    # Use a conservative explicit fixed margin for sizing when balance cannot
    # be read. The value is controlled by FALLBACK_MARGIN_USDT.
    try:
        equity = balance_usdt()
        sizing_margin = equity * MAX_MARGIN_PCT_PER_ENTRY
        balance_source = "api"
    except Exception as e:
        equity = None
        sizing_margin = FALLBACK_MARGIN_USDT
        balance_source = "fallback"
        log.warning(
            "OURBIT BALANCE READ unavailable; continuing with fallback sizing "
            "| margin=%.8f USDT | error=%s",
            sizing_margin,
            e,
        )

    if sizing_margin <= 0:
        raise OurbitError(
            f"Invalid sizing margin: {sizing_margin:.8f} USDT"
        )

    first_entry = sig.entries[0] if sig.entries else None
    first_type = sig.entry_types[0] if sig.entry_types else "limit"
    sizing_price = (
        current_price(sig.symbol)
        if first_type == "market" or first_entry is None
        else first_entry
    )

    # Size directly from the known margin budget. This avoids requiring an
    # Asset permission that Ourbit's current Read-only API does not expose.
    qty_check, notional_check, _ = exchange.size_from_margin(
        sizing_price,
        lev,
        sizing_margin,
        contract
    )

    sizing_equity = sizing_margin / MAX_MARGIN_PCT_PER_ENTRY

    log.info(
        "OURBIT SIZING OK | source=%s | margin≈%.8f USDT | first_qty=%s | "
        "first_notional≈%.8f | symbol=%s",
        balance_source,
        sizing_margin,
        qty_check,
        notional_check,
        sig.symbol
    )

    # ========================================================
    # DRY RUN
    # ========================================================

    if DRY_RUN:

        live = current_price(
            sig.symbol
        )

        log.info(
            "DRY RUN OK | source=%s | chat_id=%s | "
            "%s | direction=%s | live=%s | "
            "entries=%s | SL=%s | TP=%s | "
            "balance=%.8f | required_margin≈%.8f | "
            "max_leverage=%s | CONFIRMED=YES",
            TOOBIT_SOURCE_NAME,
            TG_SOURCE_ID,
            sig.symbol,
            sig.direction,
            live,
            sig.entries,
            sig.stop_loss,
            sig.targets,
            equity,
            required_margin,
            meta["max_leverage"]
        )

        return

    # ========================================================
    # LIVE TRADING
    # ========================================================

    try:
        exchange.change_leverage(
            sig.symbol,
            lev
        )

    except Exception as e:
        log.warning(
            "Leverage change failed/was already set: %s",
            e
        )

    for idx in range(
        min(
            MAX_ENTRIES,
            len(sig.entries)
        )
    ):

        price = sig.entries[idx]

        etype = (
            sig.entry_types[idx]
            if idx < len(sig.entry_types)
            else "limit"
        )

        if (
            idx == 0
            and etype == "market"
        ):

            price_for_size = current_price(
                sig.symbol
            )

            qty, notional, _ = calc_volume(
                price_for_size,
                lev,
                equity,
                contract
            )

            res = exchange.submit(
                sig.symbol,
                open_side(sig.direction),
                qty,
                lev,
                5,
                price=0,
                stop_loss=sig.stop_loss
            )

            log.info(
                "MARKET ENTRY sent %s qty=%s "
                "notional=%s response=%s",
                sig.symbol,
                qty,
                notional,
                res
            )

            entry_price = price_for_size

        elif price is not None:

            qty, notional, _ = calc_volume(
                price,
                lev,
                equity,
                contract
            )

            res = exchange.submit(
                sig.symbol,
                open_side(sig.direction),
                qty,
                lev,
                1,
                price=price
            )

            log.info(
                "LIMIT ENTRY %s price=%s "
                "qty=%s notional=%s "
                "response=%s",
                sig.symbol,
                price,
                qty,
                notional,
                res
            )

            entry_price = price

        else:
            continue

        key = (
            f"{sig.symbol}:"
            f"{sig.direction}:"
            f"{sig.source_message_id or 0}"
        )

        managed[key] = {
            "symbol": sig.symbol,
            "direction": sig.direction,
            "leverage": lev,
            "entry_price": entry_price,
            "stop_loss": sig.stop_loss,
            "targets": sig.targets[:3],
            "tp_done": [
                False,
                False,
                False
            ],
            "be_done": False,
            "created_message_id":
                sig.source_message_id,
        }

        save_state()

    await notify(
        f"✅ Toobit order processing started: "
        f"{sig.symbol} {sig.direction} | {lev}x"
    )


# ============================================================
# Trade manager
# ============================================================

async def manage_trade(
    key,
    trade
):
    symbol = trade["symbol"]
    direction = trade["direction"]

    targets = trade.get(
        "targets",
        []
    )[:3]

    price = current_price(
        symbol
    )

    pos = live_position(
        symbol,
        direction
    )

    if not pos:
        return

    hold = int(
        _as_float(
            extract_value(
                pos,
                "holdVol",
                "vol",
                "quantity",
                "positionVol",
                default=0
            )
        )
    )

    if hold <= 0:
        return

    if not trade.get("initial_hold"):
        trade["initial_hold"] = hold
        save_state()

    for i, target in enumerate(targets):

        if (
            trade["tp_done"][i]
            or not target_reached(
                direction,
                price,
                target
            )
        ):
            continue

        remaining = int(
            _as_float(
                extract_value(
                    pos,
                    "holdVol",
                    "vol",
                    "quantity",
                    "positionVol",
                    default=0
                )
            )
        )

        if remaining <= 0:
            trade["tp_done"][i] = True
            continue

        base = int(
            trade.get(
                "initial_hold"
            )
            or remaining
        )

        if i == 0:

            close_qty = max(
                1,
                int(
                    round(
                        base * TP1_PCT
                    )
                )
            )

        elif i == 1:

            close_qty = max(
                1,
                int(
                    round(
                        base * TP2_PCT
                    )
                )
            )

        else:

            close_qty = remaining

        close_qty = min(
            close_qty,
            remaining
        )

        res = exchange.submit(
            symbol,
            close_side(direction),
            close_qty,
            trade["leverage"],
            5,
            price=0
        )

        log.info(
            "TP%d HIT %s price=%s "
            "target=%s close_qty=%s "
            "response=%s",
            i + 1,
            symbol,
            price,
            target,
            close_qty,
            res
        )

        trade["tp_done"][i] = True
        save_state()

        if (
            i == 0
            and not trade.get("be_done")
        ):

            sid = stop_order_id(
                symbol
            )

            if sid is not None:

                try:
                    exchange.change_stop(
                        sid,
                        sl=trade["entry_price"],
                        tp=0
                    )

                    log.info(
                        "TP1 -> break-even: %s "
                        "stop_order=%s entry=%s",
                        symbol,
                        sid,
                        trade["entry_price"]
                    )

                except Exception:
                    log.exception(
                        "Failed to move SL "
                        "to break-even for %s",
                        symbol
                    )

            else:

                log.warning(
                    "TP1 hit but no stop order id "
                    "was found for %s; SL was NOT changed",
                    symbol
                )

            trade["be_done"] = True
            save_state()

        await asyncio.sleep(0.5)

        pos = live_position(
            symbol,
            direction
        )

        if not pos:
            break


async def manager_loop():

    while True:

        try:

            if not DRY_RUN:

                for key, trade in list(
                    managed.items()
                ):

                    try:
                        await manage_trade(
                            key,
                            trade
                        )

                    except Exception:
                        log.exception(
                            "Position manager failed for %s",
                            key
                        )

        except Exception:
            log.exception(
                "Position manager loop error"
            )

        await asyncio.sleep(
            max(
                1,
                POLL_SECONDS
            )
        )


# ============================================================
# Process Telegram signal
# ============================================================

async def _process_signal_message(
    event,
    edited=False
):
    text = event.raw_text or ""

    kind = (
        "EDITED MESSAGE"
        if edited
        else "MESSAGE"
    )

    log.info(
        "TOOBIT %s | source=%s | chat_id=%s | "
        "message=%s | text=%r",
        kind,
        TOOBIT_SOURCE_NAME,
        event.chat_id,
        event.id,
        text
    )

    # --------------------------------------------------------
    # HARD CONFIRMATION GATE
    # --------------------------------------------------------
    # Never execute the first/unconfirmed signal.
    # A confirmation must be explicitly published by Toobit.
    confirmed = is_confirmed_signal_text(text)

    if not confirmed:
        log.info(
            "UNCONFIRMED signal ignored | source=%s | "
            "chat_id=%s | message=%s",
            TOOBIT_SOURCE_NAME,
            event.chat_id,
            event.id
        )
        return

    log.info(
        "TOOBIT CONFIRMED | source=%s | chat_id=%s | message=%s",
        TOOBIT_SOURCE_NAME,
        event.chat_id,
        event.id
    )

    sig = parse_signal(
        text,
        event.id
    )

    if not sig:
        # Some Toobit confirmation messages may be short and contain only
        # confirmation status. In that case, the original signal must be
        # available in the edited message itself for safe execution.
        log.warning(
            "Confirmed Toobit message does not contain a complete signal; "
            "Ourbit execution blocked | message=%s",
            event.id
        )
        await notify(
            f"⚠️ Toobit confirmed, but CopyTrader blocked execution: "
            f"complete signal data was not present in message {event.id}."
        )
        return

    key = (
        sig.symbol,
        sig.direction,
        event.id
    )

    if key in seen:
        log.info(
            "Duplicate confirmed signal ignored: %s",
            key
        )
        return

    seen.add(key)

    log.info(
        "TOOBIT CONFIRMED PARSED signal "
        "direction=%s symbol=%s leverage=%s "
        "entries=%s entry_types=%s SL=%s TP=%s "
        "message=%s",
        sig.direction,
        sig.symbol,
        sig.leverage,
        sig.entries,
        sig.entry_types,
        sig.stop_loss,
        sig.targets,
        event.id
    )

    try:
        await execute(sig)

    except Exception as e:
        log.exception(
            "Confirmed signal execution failed"
        )

        await notify(
            f"❌ Confirmed Toobit signal was NOT executed on Ourbit: "
            f"{sig.symbol} {sig.direction}\n{e}"
        )


# ============================================================
# Telegram handlers
# ONLY Toobit source is listened to.
# ============================================================

@client.on(
    events.NewMessage(chats=TG_SOURCE_ID)
)
async def on_message(event):

    await _process_signal_message(
        event,
        edited=False
    )


@client.on(
    events.MessageEdited(chats=TG_SOURCE_ID)
)
async def on_message_edited(event):

    await _process_signal_message(
        event,
        edited=True
    )


# ============================================================
# Main
# ============================================================

async def main():

    load_state()

    if not TG_API_ID or not TG_API_HASH:

        raise SystemExit(
            "Set TG_API_ID and TG_API_HASH "
            "in Rawly Environment Variables."
        )

    if not TG_SESSION:

        raise SystemExit(
            "TG_SESSION is not set. "
            "Generate a Telethon StringSession "
            "and add it to Rawly Environment Variables."
        )

    log.info(
        "Toobit CopyTrader starting | "
        "source=%s | chat_id=%s | DRY_RUN=%s | "
        "Ourbit=%s",
        TOOBIT_SOURCE_NAME,
        TG_SOURCE_ID,
        DRY_RUN,
        OURBIT_API_BASE
    )

    await client.start(
        bot_token=None
    )

    me = await client.get_me()

    log.info(
        "Telegram account connected: %s",
        getattr(
            me,
            "username",
            None
        )
        or getattr(
            me,
            "id",
            None
        )
    )

    manager = asyncio.create_task(
        manager_loop()
    )

    try:

        await client.run_until_disconnected()

    finally:

        manager.cancel()


if __name__ == "__main__":
    asyncio.run(main())
