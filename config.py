import os

TG_API_ID = int(os.getenv('TG_API_ID', '0'))
TG_API_HASH = os.getenv('TG_API_HASH', '')
TG_SESSION = os.getenv('TG_SESSION', '')

# Telegram chat/channel that receives the Toobit bot's confirmed trade messages.
# It may be a numeric chat id or a public username.
TOOBIT_SOURCE = os.getenv('TOOBIT_SOURCE', '')
TG_NOTIFY_CHAT_ID = os.getenv('TG_NOTIFY_CHAT_ID', '')

OURBIT_API_BASE = os.getenv('OURBIT_API_BASE', 'https://futures.ourbit.com')
OURBIT_API_KEY = os.getenv('OURBIT_API_KEY', '')
OURBIT_API_SECRET = os.getenv('OURBIT_API_SECRET', '')

# Safety default: no real orders until Telegram parsing and Ourbit API are tested.
DRY_RUN = os.getenv('DRY_RUN', 'true').lower() in ('1', 'true', 'yes', 'on')

MAX_MARGIN_PCT_PER_ENTRY = float(os.getenv('MAX_MARGIN_PCT_PER_ENTRY', '0.06'))
DEFAULT_LEVERAGE = int(os.getenv('DEFAULT_LEVERAGE', '10'))
MARGIN_MODE = int(os.getenv('MARGIN_MODE', '1'))
POSITION_MODE = int(os.getenv('POSITION_MODE', '2'))
POLL_SECONDS = int(os.getenv('POLL_SECONDS', '3'))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '15'))
STATE_FILE = os.getenv('STATE_FILE', 'toobit_copy_state.json')

if MAX_MARGIN_PCT_PER_ENTRY <= 0 or MAX_MARGIN_PCT_PER_ENTRY > 0.06:
    raise ValueError('MAX_MARGIN_PCT_PER_ENTRY must be >0 and <= 0.06')
