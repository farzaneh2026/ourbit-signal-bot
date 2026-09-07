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
    # Entry 1 / Entry 2 lines; Persian and English labels are supported.
    for idx, pat in enumerate([
        r'(?:ENTRY\s*1|ورود\s*1)\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)',
        r'(?:ENTRY\s*2|ورود\s*2)\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)',
    ]):
        em = re.search(pat, up, re.I)
        if em:
            entries[idx] = _num(em.group(1))

    # If the signal explicitly says market on entry 1, price is optional.
    if entries[0] is not None:
        line = next((x for x in t.splitlines() if re.search(r'(ENTRY\s*1|ورود\s*1)', x, re.I)), '')
        if re.search(r'MARKET|مارکت', line, re.I):
            entry_types[0] = 'market'
        else:
            entry_types[0] = 'limit'
    if entries[1] is not None:
        entry_types[1] = 'limit'

    sl = None
    sm = re.search(r'(?:SL|STOP\s*LOSS|حد\s*ضرر)\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)', up, re.I)
    if sm:
        sl = _num(sm.group(1))

    targets = []
    # Capture target lines such as Targets: 7.744, 7.585, 7.429 or هدف 1...
    tm = re.search(r'(?:TARGETS?|اهداف?|تارگت(?:ها)?)\s*[:：]?\s*([^\n]+)', t, re.I)
    if tm:
        targets = [_num(x) for x in re.findall(r'\d+(?:\.\d+)?', tm.group(1))]
    if len(targets) < 3:
        for line in t.splitlines():
            if re.search(r'(?:TARGET|TP|تارگت|هدف)\s*[123]', line, re.I):
                nums = re.findall(r'\d+(?:\.\d+)?', line)
                if nums:
                    targets.append(_num(nums[-1]))
    # Keep first 3 unique values.
    seen = set(); clean = []
    for x in targets:
        if x not in seen:
            clean.append(x); seen.add(x)
    targets = clean[:3]

    if sl is None or not targets:
        return None
    if entries[0] is None and entries[1] is None:
        # Some messages contain only one market entry without a number.
        if re.search(r'(?:ENTRY\s*1|ورود\s*1).*MARKET|مارکت', t, re.I):
            entries[0] = None
            entry_types[0] = 'market'
        else:
            return None

    return Signal(direction, symbol, lev, entries, entry_types, sl, targets, message_id, text)
