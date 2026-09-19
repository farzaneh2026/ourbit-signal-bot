import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Signal:
    direction: str
    symbol: str
    leverage: Optional[int] = None
    entries: List[Optional[float]] = field(
        default_factory=lambda: [None, None]
    )
    entry_types: List[str] = field(
        default_factory=lambda: ['market', 'limit']
    )
    stop_loss: Optional[float] = None
    targets: List[float] = field(default_factory=list)
    source_message_id: Optional[int] = None
    raw_text: str = ''


def _num(s: str) -> float:
    return float(s.replace(',', '').strip())


def _normalize_digits(text: str) -> str:
    trans = str.maketrans(
        '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩',
        '01234567890123456789'
    )
    return text.translate(trans)


def parse_signal(
    text: str,
    message_id: int | None = None
) -> Signal | None:

    if not text:
        return None

    # Normalize punctuation/digits.
    t = text.replace('٬', ',').replace('٫', '.')
    t = _normalize_digits(t)
    up = t.upper()

    # ---------------------------------------------------------
    # DIRECTION
    # ---------------------------------------------------------
    if re.search(
        r'\b(?:LONG|BUY|لانگ|خرید)\b',
        up,
        re.I
    ) or '🟢' in up:
        direction = 'LONG'

    elif re.search(
        r'\b(?:SHORT|SELL|شورت|فروش)\b',
        up,
        re.I
    ) or '🔴' in up:
        direction = 'SHORT'

    else:
        return None

    # ---------------------------------------------------------
    # SYMBOL
    # Supports:
    # BTC/USDT
    # BTC-USDT
    # BTC_USDT
    # BTC-SWAP-USDT
    # ---------------------------------------------------------
    symbol = None

    m = re.search(
        r'\b([A-Z0-9]{2,20})[-_]SWAP[-_]USDT\b',
        up
    )
    if m:
        symbol = m.group(1) + '_USDT'

    if symbol is None:
        m = re.search(
            r'\b([A-Z0-9]{2,20})\s*/\s*USDT\b',
            up
        )
        if m:
            symbol = m.group(1) + '_USDT'

    if symbol is None:
        m = re.search(
            r'\b([A-Z0-9]{2,20})[-_]USDT\b',
            up
        )
        if m:
            symbol = m.group(1) + '_USDT'

    if symbol is None:
        return None

    # ---------------------------------------------------------
    # LEVERAGE
    # ---------------------------------------------------------
    lev = None

    lm = re.search(
        r'(?:LEVERAGE|اهرم)\s*[:：]?\s*(\d+)\s*[xX×]?',
        up,
        re.I
    )

    if lm:
        lev = int(lm.group(1))

    # ---------------------------------------------------------
    # ENTRIES
    # ---------------------------------------------------------
    entries = [None, None]
    entry_types = ['market', 'limit']

    # Old format:
    # Entry 1: 123
    # Entry 2: 124
    #
    # Persian:
    # ورود 1: 123
    # ورود 2: 124
    for idx, pat in enumerate([
        r'(?:ENTRY\s*1|ورود\s*1)\s*[:：]?\s*'
        r'([0-9]+(?:\.[0-9]+)?)',

        r'(?:ENTRY\s*2|ورود\s*2)\s*[:：]?\s*'
        r'([0-9]+(?:\.[0-9]+)?)',
    ]):

        em = re.search(pat, up, re.I)

        if em:
            entries[idx] = _num(em.group(1))

    # ---------------------------------------------------------
    # NEW TOOBIT FORMAT
    #
    # Entry: 81108.07
    #
    # This is the main missing part in the old parser.
    # ---------------------------------------------------------
    if entries[0] is None:

        em = re.search(
            r'^\s*ENTRY\s*[:：]\s*'
            r'([0-9]+(?:\.[0-9]+)?)',
            up,
            re.MULTILINE | re.I
        )

        if em:
            entries[0] = _num(em.group(1))
            entry_types[0] = 'limit'

    # Persian single entry:
    # ورود: 123
    if entries[0] is None:

        em = re.search(
            r'^\s*ورود\s*[:：]\s*'
            r'([0-9]+(?:\.[0-9]+)?)',
            up,
            re.MULTILINE
        )

        if em:
            entries[0] = _num(em.group(1))
            entry_types[0] = 'limit'

    # Detect MARKET entry.
    entry1_line = next(
        (
            x for x in t.splitlines()
            if re.search(
                r'(?:ENTRY\s*1|ENTRY\s*:|ورود\s*1|ورود\s*:)',
                x,
                re.I
            )
        ),
        ''
    )

    if re.search(r'MARKET|مارکت', entry1_line, re.I):
        entry_types[0] = 'market'

    # ---------------------------------------------------------
    # STOP LOSS
    # ---------------------------------------------------------
    sl = None

    sm = re.search(
        r'(?:SL|STOP\s*LOSS|حد\s*ضرر)\s*'
        r'[:：]?\s*([0-9]+(?:\.[0-9]+)?)',
        up,
        re.I
    )

    if sm:
        sl = _num(sm.group(1))

    # ---------------------------------------------------------
    # TARGETS
    # ---------------------------------------------------------
    targets = []

    # NEW TOOBIT FORMAT:
    #
    # TP (Full / 2R): 81405.21
    #
    # Also supports:
    # TP: 81405.21
    # Take Profit: 81405.21
    # ---------------------------------------------------------

    tp_patterns = [
        r'TP\s*\([^)]*\)\s*[:：]\s*'
        r'([0-9]+(?:\.[0-9]+)?)',

        r'^\s*TP\s*[:：]\s*'
        r'([0-9]+(?:\.[0-9]+)?)',

        r'TAKE\s*PROFIT\s*[:：]\s*'
        r'([0-9]+(?:\.[0-9]+)?)',
    ]

    for pat in tp_patterns:

        tm = re.search(
            pat,
            up,
            re.MULTILINE | re.I
        )

        if tm:
            targets.append(_num(tm.group(1)))
            break

    # ---------------------------------------------------------
    # OLD TARGET BLOCK
    # ---------------------------------------------------------
    if not targets:

        tm = re.search(
            r'(?:TARGETS?|اهداف?|تارگت(?:ها)?)\s*[:：]?',
            t,
            re.I
        )

        if tm:

            block = t[tm.end():]

            for line in block.splitlines()[:8]:

                if not line.strip():
                    if targets:
                        break
                    continue

                # Remove emoji numbering:
                # 1️⃣ 2️⃣ 3️⃣
                line = re.sub(
                    r'[0-9]\ufe0f?\u20e3',
                    ' ',
                    line
                )

                vals = re.findall(
                    r'\d+(?:\.\d+)?',
                    line
                )

                if vals:
                    targets.extend(
                        _num(x) for x in vals
                    )

                elif targets and re.search(
                    r'(?:STOP|SL|حد\s*ضرر)',
                    line,
                    re.I
                ):
                    break

    # ---------------------------------------------------------
    # Remove duplicate targets
    # ---------------------------------------------------------
    seen = set()
    clean = []

    for x in targets:

        if x not in seen:
            clean.append(x)
            seen.add(x)

    targets = clean[:3]

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------
    if sl is None:
        return None

    if not targets:
        return None

    if entries[0] is None and entries[1] is None:

        # Market-only message.
        if re.search(
            r'(?:ENTRY\s*1|ورود\s*1).*MARKET|'
            r'(?:ENTRY\s*:|ورود\s*:).*MARKET|'
            r'مارکت',
            t,
            re.I
        ):
            entries[0] = None
            entry_types[0] = 'market'

        else:
            return None

    # ---------------------------------------------------------
    # FINAL SIGNAL
    # ---------------------------------------------------------
    return Signal(
        direction=direction,
        symbol=symbol,
        leverage=lev,
        entries=entries,
        entry_types=entry_types,
        stop_loss=sl,
        targets=targets,
        source_message_id=message_id,
        raw_text=text
    )
