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


def _num(s: str) -> float:
    return float(s.replace(',', '').strip())


def _extract_price_values(text: str) -> list[float]:
    """Extract decimal/integer price-like values without treating labels as prices."""
    values = []
    for m in re.finditer(r'(?<![A-Za-z0-9_])\d+(?:\.\d+)?(?![A-Za-z0-9_])', text):
        try:
            values.append(_num(m.group(0)))
        except ValueError:
            continue
    return values


def _extract_target_line_values(line: str) -> list[float]:
    """Extract TP price from a target line, ignoring TP/target numbering and percentages/R multiples."""
    # Remove the target label/ordinal first: TP1, TP 1, TARGET 1, هدف 1, etc.
    cleaned = re.sub(
        r'^\s*(?:TARGETS?|TP|تارگت(?:ها)?|هدف(?:ها)?)\s*[123]?\s*[-:：=]?\s*',
        '', line, flags=re.I
    )
    # Remove common percentage/R:R annotations which are not prices.
    cleaned = re.sub(r'\b\d+(?:\.\d+)?\s*R\b', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\b\d+(?:\.\d+)?\s*%\b', '', cleaned)
    vals = _extract_price_values(cleaned)
    return vals


def parse_signal(text: str, message_id: int | None = None) -> Signal | None:
    t = text.replace('٬', ',').replace('٫', '.')
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
    # First, parse explicit TP/Target lines. This avoids accidentally treating
    # the target number (e.g. the "1" in TP1) or an R-multiple as the TP price.
    for line in t.splitlines():
        if re.search(r'^\s*(?:TARGETS?|TP|تارگت(?:ها)?|هدف(?:ها)?)\s*[123]?\s*[-:：=]', line, re.I):
            vals = _extract_target_line_values(line)
            if vals:
                # For a single TP line use the first actual price. For a Targets
                # list, retain all values on that line.
                targets.extend(vals)

    # Also support inline labels such as "TP1 11.70 TP2 11.50 TP3 11.30".
    if not targets:
        for m in re.finditer(
            r'(?:TARGET|TP|تارگت|هدف)\s*([123])\s*[:：=\-]?\s*([0-9]+(?:\.[0-9]+)?)',
            t, re.I
        ):
            targets.append(_num(m.group(2)))

    # Fallback for a Targets: ... line when it does not start with a standard
    # delimiter. Strip the label before extracting numbers so "Targets 1.0R ..."
    # cannot become TP=1.0.
    if not targets:
        tm = re.search(r'(?:TARGETS?|اهداف?|تارگت(?:ها)?|هدف(?:ها)?)\s*[:：]?\s*([^\n]+)', t, re.I)
        if tm:
            cleaned = re.sub(r'\b\d+(?:\.\d+)?\s*R\b', '', tm.group(1), flags=re.I)
            cleaned = re.sub(r'\b\d+(?:\.\d+)?\s*%\b', '', cleaned)
            targets = _extract_price_values(cleaned)

    # Keep first 3 unique values in signal order.
    seen_values = set()
    clean = []
    for x in targets:
        if x not in seen_values:
            clean.append(x)
            seen_values.add(x)
    targets = clean[:3]

    if sl is None or not targets:
        return None

    if entries[0] is None and entries[1] is None:
        # Market entry may be expressed without a numeric price.
        if re.search(r'(?:ENTRY\s*1|ورود\s*1).*MARKET|مارکت', t, re.I):
            entries[0] = None
            entry_types[0] = 'market'
        else:
            # Some Otis messages use a bare "MARKET" entry without ENTRY 1.
            if re.search(r'\bMARKET\b|مارکت', t, re.I):
                entries[0] = None
                entry_types[0] = 'market'
            else:
                return None

    sig = Signal(direction, symbol, lev, entries, entry_types, sl, targets, message_id, text)
    return sig
