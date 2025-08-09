import sys
import os
import json
import time
import yaml
import requests
import http.cookiejar as cookiejar
from requests.compat import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------- Paths (next to script) ----------
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_COOKIES = os.path.join(HERE, "gym_api_state.lwp")
STATE_INFO    = os.path.join(HERE, "gym_api_info.json")

# ---------- Tuning ----------
CACHE_TTL_SECONDS = 900        # 15 minutes
MIN_LOGIN_RETRY_SECONDS = 300  # avoid hammering login on repeated failures

class GymGroupAPI:
    BASE_URL = 'https://thegymgroup.netpulse.com/np/'
    ENDPOINT_LOGIN = 'exerciser/login'
    HEADERS = {
        'Accept': 'application/json',
        'User-Agent': 'okhttp/4.12.0',
        'X-NP-API-Version': '1.5',
        'X-NP-App-Version': '9999.0',
        "X-NP-User-Agent": (
            "clientType=MOBILE_DEVICE; "
            "devicePlatform=ANDROID; "
            "deviceUid=; "
            "applicationName=The Gym Group; "
            "applicationVersion=9999.0; "
            "applicationVersionCode=999999"
        )
    }

    def __init__(self, username, password):
        self.username   = username
        self.password   = password
        self.user_id    = None
        self.home_gym   = None
        self.etag       = None
        self.last_value = None
        self.last_ts    = 0.0
        self.last_login_attempt = 0.0

        self.session = requests.Session()
        self.session.headers.update(self._strip_accept_encoding(self.HEADERS))

        # --- Silent HTTP retry adapter (handles brief blips without noise) ---
        retries = Retry(
            total=2,
            backoff_factor=0.5,  # ~0.5s then ~1s
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"])
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Persist cookies with domain/path
        self.session.cookies = cookiejar.LWPCookieJar(STATE_COOKIES)
        try:
            self.session.cookies.load(ignore_discard=True, ignore_expires=False)
        except FileNotFoundError:
            pass
        except Exception:
            # corrupted jar -> start fresh silently
            self.session.cookies = cookiejar.LWPCookieJar(STATE_COOKIES)

        self._load_info()

    @staticmethod
    def _strip_accept_encoding(h):
        h2 = dict(h)
        h2.pop('Accept-Encoding', None)
        return h2

    # ----- State I/O -----
    def _load_info(self):
        try:
            with open(STATE_INFO, 'r') as f:
                d = json.load(f)
            self.user_id    = d.get('user_id')
            self.home_gym   = d.get('home_gym')
            self.etag       = d.get('etag')
            self.last_value = d.get('last_value')
            self.last_ts    = float(d.get('last_ts', 0))
            self.last_login_attempt = float(d.get('last_login_attempt', 0))
        except Exception:
            self.user_id = self.home_gym = self.etag = None
            self.last_value, self.last_ts, self.last_login_attempt = None, 0.0, 0.0

    def _save_info(self):
        try:
            tmp = f"{STATE_INFO}.tmp"
            payload = {
                'user_id': self.user_id,
                'home_gym': self.home_gym,
                'etag': self.etag,
                'last_value': self.last_value,
                'last_ts': self.last_ts,
                'last_login_attempt': self.last_login_attempt,
            }
            with open(tmp, 'w') as f:
                json.dump(payload, f)
            os.replace(tmp, STATE_INFO)
            try:
                os.chmod(STATE_INFO, 0o600)
            except Exception:
                pass
        except Exception:
            pass

    def _save_cookies(self):
        try:
            self.session.cookies.save(ignore_discard=True, ignore_expires=True)
        except Exception:
            pass

    # ----- HTTP -----
    def _api(self, method, endpoint, *, headers=None, data=None, retry_auth=True):
        url = urljoin(self.BASE_URL, endpoint)
        try:
            if method == 'GET':
                resp = self.session.get(url, headers=headers, timeout=15)
            else:
                resp = self.session.post(url, data=data, headers=headers, timeout=15)
            if resp.status_code in (401, 403) and retry_auth:
                if self._maybe_login():
                    return self._api(method, endpoint, headers=headers, data=data, retry_auth=False)
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            raise Exception(str(e))

    # ----- Auth -----
    def _maybe_login(self):
        now = time.time()
        if now - self.last_login_attempt < MIN_LOGIN_RETRY_SECONDS:
            return False
        self.last_login_attempt = now
        self._save_info()
        return self.login()

    def login(self):
        try:
            resp = self._api('POST', self.ENDPOINT_LOGIN,
                             data={'username': self.username, 'password': self.password},
                             retry_auth=False)
            info = resp.json()
            self.user_id = info['uuid']
            self.home_gym = info['homeClubUuid']
            self._save_cookies()
            self._save_info()
            return True
        except Exception:
            return False

    # ----- API -----
    def get_gym_occupancy(self):
        now = time.time()
        # Serve cached value if within TTL
        if self.last_value is not None and (now - self.last_ts) < CACHE_TTL_SECONDS:
            return self.last_value

        if not self.user_id or not self.home_gym:
            if not self._maybe_login():
                if self.last_value is not None:
                    return self.last_value
                raise Exception("Login required and throttled/failed")

        endpoint = f"thegymgroup/v1.0/exerciser/{self.user_id}/gym-busyness?gymLocationId={self.home_gym}"
        hdrs = {}
        if self.etag:
            hdrs['If-None-Match'] = self.etag

        resp = self._api('GET', endpoint, headers=hdrs)

        if resp.status_code == 304 and self.last_value is not None:
            self.last_ts = now
            self._save_info()
            return self.last_value

        data = resp.json()

        # PEOPLE COUNT parsing (no clamping)
        raw = data.get('currentCapacity')
        try:
            num = int(float(str(raw)))
        except Exception:
            num = None

        new_etag = resp.headers.get('ETag') or resp.headers.get('Etag')
        if new_etag:
            self.etag = new_etag

        if num is not None:
            self.last_value = num
            self.last_ts = now
            self._save_info()
            return self.last_value

        # if API response is weird, keep previous value if we have one
        if self.last_value is not None:
            self.last_ts = now
            self._save_info()
            return self.last_value

        raise Exception("Occupancy missing and no cached value")

# ----- Entry point -----
if __name__ == "__main__":
    secrets_path = '/config/secrets.yaml'
    try:
        with open(secrets_path) as f:
            secrets = yaml.safe_load(f)
        USERNAME = secrets['gym_group_username']
        PASSWORD = secrets['gym_group_password']
    except Exception as e:
        print(f"Error: secrets problem: {e}", file=sys.stderr)
        sys.exit(1)

    api = GymGroupAPI(USERNAME, PASSWORD)
    try:
        value = api.get_gym_occupancy()
        print(value)  # stdout ONLY the number (HA-safe)
    except Exception as e:
        if api.last_value is not None:
            print(api.last_value)  # final fallback: last known people count
            sys.exit(0)
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
