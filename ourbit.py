import hashlib
import hmac
import json
import time
import uuid
import socket
from urllib.parse import urlparse
from decimal import Decimal, ROUND_UP
from typing import Any
import requests

from config import (
    OURBIT_API_BASE, OURBIT_API_KEY, OURBIT_API_SECRET,
    REQUEST_TIMEOUT, MARGIN_MODE, POSITION_MODE,
)


class OurbitError(RuntimeError):
    pass


def _unwrap(data):
    if isinstance(data, dict) and 'data' in data:
        return data['data']
    return data


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _find_records(obj):
    """Flatten common Ourbit response shapes into dict records."""
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ('data', 'list', 'result', 'rows', 'contracts', 'items'):
            if key in obj:
                found = _find_records(obj[key])
                if found:
                    return found
        return [obj]
    return []


class OurbitClient:
    def __init__(self):
        self.base = OURBIT_API_BASE.rstrip('/')
        self.key = OURBIT_API_KEY
        self.secret = OURBIT_API_SECRET
        self.s = requests.Session()
        self.s.headers.update({'User-Agent': 'otis-copytrader/2.0'})
        self._last_health = None

    def _require_keys(self):
        if not self.key or not self.secret:
            raise OurbitError('OURBIT_API_KEY / OURBIT_API_SECRET are not configured')

    def _signed_headers(self, method: str, payload: Any = None, query_string: str = ''):
        self._require_keys()
        ts = str(int(time.time() * 1000))
        if method.upper() == 'POST':
            raw = json.dumps(payload if payload is not None else {}, separators=(',', ':'), ensure_ascii=False)
            message = self.key + ts + raw
        else:
            message = self.key + ts + (query_string or '')
        sig = hmac.new(self.secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        return {
            'Request-Time': ts,
            'ApiKey': self.key,
            'Signature': sig,
            'Content-Type': 'application/json',
        }

    @staticmethod
    def _query_string(params):
        if not params:
            return ''
        # Match the V1 Postman collection convention: key=value pairs in request order.
        return '&'.join(f'{k}={v}' for k, v in params.items() if v is not None)

    def _request(self, method, path, *, params=None, payload=None, private=False):
        url = self.base + path
        params = params or {}
        try:
            if method.upper() == 'GET':
                headers = self._signed_headers('GET', query_string=self._query_string(params)) if private else {}
                r = self.s.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
            else:
                payload = payload if payload is not None else {}
                headers = self._signed_headers('POST', payload) if private else {'Content-Type': 'application/json'}
                body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
                r = self.s.post(url, data=body, headers=headers, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout as e:
            raise OurbitError(f'Ourbit timeout calling {url}: {e}') from e
        except requests.exceptions.ConnectionError as e:
            host = urlparse(url).hostname or self.base
            dns_hint = ''
            try:
                socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            except socket.gaierror as de:
                dns_hint = f' DNS lookup also failed for {host}: {de}.'
            raise OurbitError(f'Ourbit DNS/connection error calling {url}: {e}.{dns_hint} Check Railway network/DNS and OURBIT_API_BASE.') from e
        except requests.exceptions.RequestException as e:
            raise OurbitError(f'Ourbit request error calling {url}: {e}') from e
        return self._json(r)

    def get(self, path, params=None, private=False):
        return self._request('GET', path, params=params, private=private)

    def post(self, path, payload=None, private=True):
        return self._request('POST', path, payload=payload, private=private)

    @staticmethod
    def _json(r):
        try:
            data = r.json()
        except Exception:
            data = {'http_status': r.status_code, 'text': r.text}
        if r.status_code >= 400:
            raise OurbitError(f'HTTP {r.status_code}: {data}')
        if isinstance(data, dict):
            if data.get('success') is False:
                raise OurbitError(str(data))
            code = data.get('code')
            if code not in (None, 0, 200, '0', '200') and data.get('msg'):
                raise OurbitError(str(data))
        return data

    def ping(self):
        return self.get('/api/v1/contract/ping')

    def health_check(self):
        """Check official V1 contract API and report DNS status without raising."""
        host = urlparse(self.base).hostname or ''
        result = {'base': self.base, 'host': host, 'dns': False, 'api': False, 'error': None}
        try:
            socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            result['dns'] = True
        except socket.gaierror as e:
            result['error'] = f'DNS lookup failed: {e}'
            self._last_health = result
            return result
        try:
            self.ping()
            result['api'] = True
        except OurbitError as e:
            result['error'] = str(e)
        self._last_health = result
        return result

    def diagnostic_dns(self, hosts=None):
        """Resolve candidate Ourbit hosts for diagnosis only; never switches API base."""
        hosts = hosts or ['contract.ourbit.com', 'api.ourbit.com', 'futures.ourbit.com']
        out = {}
        for host in hosts:
            try:
                addrs = sorted({x[4][0] for x in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
                out[host] = {'ok': True, 'addresses': addrs}
            except socket.gaierror as e:
                out[host] = {'ok': False, 'error': str(e)}
        return out

    def diagnostic_http_bases(self, symbol='BTC_USDT'):
        """Test public V1 paths on alternate Ourbit hosts; never changes self.base and never trades."""
        hosts = ['api.ourbit.com', 'futures.ourbit.com']
        paths = [
            '/api/v1/contract/ping',
            '/api/v1/contract/detail',
        ]
        out = {}
        for host in hosts:
            base = f'https://{host}'
            out[host] = {}
            for path in paths:
                url = base + path
                params = {'symbol': symbol} if path.endswith('/detail') else None
                try:
                    r = self.s.get(url, params=params, timeout=REQUEST_TIMEOUT)
                    content_type = r.headers.get('content-type', '')
                    body = r.text[:500]
                    out[host][path] = {
                        'ok': 200 <= r.status_code < 400,
                        'status': r.status_code,
                        'content_type': content_type,
                        'body': body,
                    }
                except requests.exceptions.RequestException as e:
                    out[host][path] = {'ok': False, 'error': str(e)}
        return out

    def contract_detail(self, symbol=None):
        params = {'symbol': symbol} if symbol else {}
        return self.get('/api/v1/contract/detail', params)

    def contract_for(self, symbol):
        data = self.contract_detail(symbol)
        records = _find_records(data)
        wanted = symbol.upper()
        for r in records:
            s = str(r.get('symbol', r.get('contractSymbol', ''))).upper()
            if s == wanted:
                return r
        # Some installations return all contracts under data even when symbol is passed.
        for r in records:
            if wanted.replace('_', '') == str(r.get('symbol', '')).upper().replace('_', ''):
                return r
        raise OurbitError(f'Ourbit contract detail not found for {symbol}')

    def ticker(self, symbol):
        return self.get('/api/v1/contract/ticker', {'symbol': symbol})

    def assets(self):
        return self.get('/api/v1/private/account/assets', private=True)

    def asset_usdt(self):
        return self.get('/api/v1/private/account/asset/USDT', private=True)

    def change_leverage(self, symbol, leverage):
        return self.post('/api/v1/private/position/change_leverage', {
            'openType': MARGIN_MODE,
            'leverage': int(leverage),
            'symbol': symbol,
            'positionType': 1,
        })

    def submit(self, symbol, side, vol, leverage, order_type, price=0, external_oid=None,
               stop_loss=None, take_profit=None, position_id=None):
        p = {
            'symbol': symbol,
            'price': str(price or 0),
            'vol': int(vol),
            'leverage': int(leverage),
            'side': int(side),
            'type': int(order_type),
            'openType': int(MARGIN_MODE),
            'positionMode': int(POSITION_MODE),
            'externalOid': external_oid or ('otis-' + uuid.uuid4().hex[:18]),
        }
        if position_id is not None:
            p['positionId'] = int(position_id)
        if stop_loss is not None:
            p['stopLossPrice'] = str(stop_loss)
        if take_profit is not None:
            p['takeProfitPrice'] = str(take_profit)
        return self.post('/api/v1/private/order/submit', p)

    def open_orders(self, symbol):
        return self.get(f'/api/v1/private/order/list/open_orders/{symbol}',
                        {'page_num': 1, 'page_size': 100}, private=True)

    def history_orders(self, symbol):
        return self.get('/api/v1/private/order/list/history_orders',
                        {'page_num': 1, 'page_size': 100, 'symbol': symbol}, private=True)

    def positions(self, symbol=None):
        p = {'page_num': 1, 'page_size': 100}
        if symbol:
            p['symbol'] = symbol
        return self.get('/api/v1/private/position/list/history_positions', p, private=True)

    def stop_orders(self, symbol=None):
        p = {'page_num': 1, 'page_size': 100}
        if symbol:
            p['symbol'] = symbol
        return self.get('/api/v1/private/stoporder/list/orders', p, private=True)

    def plan_orders(self, symbol=None):
        p = {'page_num': 1, 'page_size': 100}
        if symbol:
            p['symbol'] = symbol
        return self.get('/api/v1/private/planorder/list/orders', p, private=True)

    def change_stop(self, order_id, sl=None, tp=None):
        return self.post('/api/v1/private/stoporder/change_price', {
            'orderId': str(order_id),
            'stopLossPrice': str(sl or 0),
            'takeProfitPrice': str(tp or 0),
        })

    def cancel(self, order_ids):
        return self.post('/api/v1/private/order/cancel', list(order_ids))

    def cancel_all(self, symbol):
        return self.post('/api/v1/private/order/cancel_all', {'symbol': symbol})

    def cancel_stop(self, stop_ids):
        return self.post('/api/v1/private/stoporder/cancel', [
            {'stopPlanOrderId': str(x)} for x in stop_ids
        ])

    @staticmethod
    def normalize_contract(detail):
        """Return contract sizing fields from flexible V1 response names."""
        def pick(*keys, default=None):
            for k in keys:
                if k in detail and detail[k] not in (None, ''):
                    return detail[k]
            return default

        size = _as_float(pick('contractSize', 'contract_size', 'futuresSize', 'multiplier', default=1), 1)
        min_vol = _as_float(pick('minVol', 'minVolume', 'minQty', 'quantityMin', 'minOrderQty', default=1), 1)
        vol_unit = _as_float(pick('volUnit', 'volumeUnit', 'qtyStep', 'stepSize', 'quantityStep', default=1), 1)
        min_amount = _as_float(pick('minAmount', 'minNotional', 'minOrderAmount', 'min_order_amount', default=0), 0)
        max_vol = _as_float(pick('maxVol', 'maxVolume', 'maxQty', 'quantityMax', 'maxOrderQty', default=0), 0)
        price_unit = _as_float(pick('priceUnit', 'priceStep', 'tickSize', default=0), 0)
        max_lev = _as_float(pick('maxLeverage', 'max_leverage', default=200), 200)
        return {
            'contract_size': size if size > 0 else 1,
            'min_vol': max(1, int(min_vol)),
            'vol_unit': max(1, int(vol_unit)),
            'min_amount': max(0, min_amount),
            'max_vol': max(0, int(max_vol)),
            'price_unit': price_unit,
            'max_leverage': max(1, int(max_lev)),
        }

    @staticmethod
    def size_from_margin(price, leverage, margin, detail):
        c = OurbitClient.normalize_contract(detail)
        if price <= 0 or leverage <= 0 or margin <= 0:
            raise OurbitError('Invalid price/leverage/margin for sizing')
        raw = (margin * leverage) / (price * c['contract_size'])
        step = Decimal(c['vol_unit'])
        qty = int((Decimal(str(raw)) / step).to_integral_value(rounding=ROUND_UP) * step)
        qty = max(qty, c['min_vol'])
        if c['max_vol'] and qty > c['max_vol']:
            qty = c['max_vol'] - (c['max_vol'] % c['vol_unit'])
        if qty <= 0:
            raise OurbitError('Calculated quantity is not valid for this contract')
        notional = qty * price * c['contract_size']
        if c['min_amount'] and notional < c['min_amount']:
            needed = Decimal(str(c['min_amount'])) / (Decimal(str(price)) * Decimal(str(c['contract_size'])))
            qty = int((needed / step).to_integral_value(rounding=ROUND_UP) * step)
            qty = max(qty, c['min_vol'])
            notional = qty * price * c['contract_size']
        return qty, notional, c
