import os

TG_API_ID = int(os.getenv('TG_API_ID', '0'))
TG_API_HASH = os.getenv('TG_API_HASH', '')
TG_SESSION = os.getenv('TG_SESSION', '')
TG_SOURCE = os.getenv('TG_SOURCE', '-1003980416205')
TG_NOTIFY_CHAT_ID = os.getenv('TG_NOTIFY_CHAT_ID', '')

OURBIT_API_BASE = os.getenv('OURBIT_API_BASE', 'https://contract.ourbit.com')
OURBIT_API_FALLBACK_BASES = [x.strip().rstrip('/') for x in os.getenv('OURBIT_API_FALLBACK_BASES', '').split(',') if x.strip()]
OURBIT_API_KEY = os.getenv('OURBIT_API_KEY', '')
OURBIT_API_SECRET = os.getenv('OURBIT_API_SECRET', '')

# Safety default: no real orders until API + parser have been tested.
DRY_RUN = os.getenv('DRY_RUN', 'true').lower() in ('1', 'true', 'yes', 'on')

MAX_MARGIN_PCT_PER_ENTRY = float(os.getenv('MAX_MARGIN_PCT_PER_ENTRY', '0.06'))
MAX_ENTRIES = int(os.getenv('MAX_ENTRIES', '2'))
DEFAULT_LEVERAGE = int(os.getenv('DEFAULT_LEVERAGE', '10'))
MARGIN_MODE = int(os.getenv('MARGIN_MODE', '1'))
POSITION_MODE = int(os.getenv('POSITION_MODE', '2'))

TP1_PCT = float(os.getenv('TP1_PCT', '0.30'))
TP2_PCT = float(os.getenv('TP2_PCT', '0.30'))
TP3_PCT = float(os.getenv('TP3_PCT', '0.40'))
POLL_SECONDS = int(os.getenv('POLL_SECONDS', '3'))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '15'))
STATE_FILE = os.getenv('STATE_FILE', 'otis_state.json')

if MAX_MARGIN_PCT_PER_ENTRY <= 0 or MAX_MARGIN_PCT_PER_ENTRY > 0.06:
    raise ValueError('MAX_MARGIN_PCT_PER_ENTRY must be >0 and <= 0.06')
if TP1_PCT + TP2_PCT + TP3_PCT > 1.000001:
    raise ValueError('TP percentages must not exceed 100%')
