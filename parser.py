import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Signal:
    direction: str
    symbol: str
    leverage: Optional[int] = None
    entries: List[Optional[float]] = field(default_factory=lambda: [None, None])
    entry_types: List[str] = field(default_factory=lambda: ['market', 'limit'])
    stop_loss: Optional[float] = None
    targets: List[float] = field(default_factory=list)
    source_message_id: Optional[int] = None
    raw_text: str = ''


def _normalize_digits(text: str) -> str:
    """Convert Persian/Arabic-Indic digits to ASCII digits for reliable regex parsing."""
    trans = str.maketrans(
        '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩',
        '01234567890123456789',
    )
    return text.translate(trans)


def _num(s: str) -> float:
    return float(s.replace(',', '').strip())


def _extract_price_values(text: str) -> list[float]:
    """Extract numeric price-like values without treating labels as prices."""
    values = []
    for m in re.finditer(r'(?<![A-Za-z0-9_])\d+(?:\.\d+)?(?![A-Za-z0-9_])', text):
        try:
            values.append(_num(m.group(0)))
        except ValueError:
            continue
    return values


def _extract_target_line_values(line: str) -> list[float]:
    """Extract actual target prices from a target line, ignoring numbering/percent/R values."""
    cleaned = re.sub(
        r'^\s*(?:TARGETS?|TP|تارگت(?:\s*ها)?|هدف(?:\s*ها)?)\s*[1-4]?\s*[-:：=]?\s*',
        '', line, flags=re.I
    )
    cleaned = re.sub(r'\b\d+(?:\.\d+)?\s*R\b', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\b\d+(?:\.\d+)?\s*%', '', cleaned)
    return _extract_price_values(cleaned)


def _extract_target_block(lines: list[str], header_index: int) -> list[float]:
    """Read the numeric target lines following a 'تارگت ها:' / 'Targets:' header."""
    values = []
    for line in lines[header_index + 1:]:
        stripped = line.strip()
        if not stripped:
            if values:
                break
            continue

        # A new section/header means the target block is finished.
        if re.search(r'(?:حد\s*ضرر|STOP\s*LOSS|SL|ورود|ENTRY|اهرم|LEVERAGE)', stripped, re.I):
            break

        nums = _extract_price_values(stripped)
        if not nums:
            # Ignore decorative/emoji-only lines while we are still in the block.
            if values:
                break
            continue

        # In the Otis format each target line is like '0.940 1️⃣'.
        # The first decimal/price is the target; the trailing number is just its ordinal.
        price = None
        for n in nums:
            if '.' in str(n):
                price = n
                break
        if price is None:
            # Accept a plain integer target only when the line contains no ordinal-like
            # second number. This keeps labels such as '1 2 3' from becoming prices.
            if len(nums) == 1:
                price = nums[0]
            else:
                continue
        values.append(price)

        # Otis currently publishes four target levels.
        if len(values) >= 4:
            break
    return values


def parse_signal(text: str, message_id: int | None = None) -> Signal | None:
    # Normalize decimal separators and Persian/Arabic-Indic digits first.
    t = _normalize_digits(text or '').replace('٬', ',').replace('٫', '.')
    up = t.upper()

    if re.search(r'\b(?:LONG|BUY|لانگ|خرید)\b|🟢', up):
        direction = 'LONG'
    elif re.search(r'\b(?:SHORT|SELL|شورت|فروش)\b|🔴', up):
        direction = 'SHORT'
    else:
        return None

    m = re.search(r'\b([A-Z0-9]{2,15})\s*/\s*USDT\b', up)
    if not m:
        m = re.search(r'\b([A-Z0-9]{2,15})[-_]USDT\b', up)
    if not m:
        return None
    symbol = m.group(1) + '_USDT'

    lev = None
    lm = re.search(r'(?:LEVERAGE|اهرم)\s*[:：]?\s*(\d+)\s*[xX×]?', up, re.I)
    if lm:
        lev = int(lm.group(1))

    entries = [None, None]
    entry_types = ['market', 'limit']
    for idx, pat in enumerate([
        r'(?:ENTRY\s*1|ورود\s*1)\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)',
        r'(?:ENTRY\s*2|ورود\s*2)\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)',
    ]):
        em = re.search(pat, up, re.I)
        if em:
            entries[idx] = _num(em.group(1))

    if entries[0] is not None:
        line = next((x for x in t.splitlines() if re.search(r'(ENTRY\s*1|ورود\s*1)', x, re.I)), '')
        entry_types[0] = 'market' if re.search(r'MARKET|مارکت', line, re.I) else 'limit'
    if entries[1] is not None:
        entry_types[1] = 'limit'

    sl = None
    sm = re.search(r'(?:SL|STOP\s*LOSS|حد\s*ضرر)\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)', up, re.I)
    if sm:
        sl = _num(sm.group(1))

    targets = []
    lines = t.splitlines()

    # Explicit target lines such as 'TP1: 0.940'.
    for line in lines:
        if re.search(r'(?:TARGETS?|TP|تارگت(?:\s*ها)?|هدف(?:\s*ها)?)\s*[1-4]?\s*[-:：=]', line, re.I):
            vals = _extract_target_line_values(line)
            if vals:
                targets.extend(vals)

    # Otis format: 'تارگت ها:' followed by one price per line, often with emoji ordinals.
    if not targets:
        for i, line in enumerate(lines):
            if re.search(r'(?:TARGETS?|اهداف?|تارگت(?:\s*ها)?|هدف(?:\s*ها)?)\s*[:：]?\s*$', line, re.I):
                targets.extend(_extract_target_block(lines, i))
                if targets:
                    break

    # Inline labels such as 'TP1 11.70 TP2 11.50 TP3 11.30 TP4 11.10'.
    if not targets:
        for m in re.finditer(
            r'(?:TARGET|TP|تارگت|هدف)\s*([1-4])\s*[:：=\-]?\s*([0-9]+(?:\.[0-9]+)?)',
            t, re.I
        ):
            targets.append(_num(m.group(2)))

    # Fallback for a 'Targets: ...' line.
    if not targets:
        tm = re.search(r'(?:TARGETS?|اهداف?|تارگت(?:\s*ها)?|هدف(?:\s*ها)?)\s*[:：]?\s*([^\n]+)', t, re.I)
        if tm:
            cleaned = re.sub(r'\b\d+(?:\.\d+)?\s*R\b', '', tm.group(1), flags=re.I)
            cleaned = re.sub(r'\b\d+(?:\.\d+)?\s*%', '', cleaned)
            targets = _extract_price_values(cleaned)

    # Keep unique targets in signal order. Do not arbitrarily discard TP4.
    seen_values = set()
    clean = []
    for x in targets:
        if x not in seen_values:
            clean.append(x)
            seen_values.add(x)
    targets = clean[:4]

    if sl is None or not targets:
        return None

    if entries[0] is None and entries[1] is None:
        # Market entry may be expressed without a numeric price.
        if re.search(r'(?:ENTRY\s*1|ورود\s*1).*MARKET|مارکت', t, re.I):
            entry_types[0] = 'market'
        elif re.search(r'\bMARKET\b|مارکت', t, re.I):
            entry_types[0] = 'market'
        else:
            return None

    return Signal(direction, symbol, lev, entries, entry_types, sl, targets, message_id, text)
