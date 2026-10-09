# =============================================================================
# Net-monit V10.7
# Copyright (c) 2024-2026 Abdullah | Abdullah-InfoXtek.com
# Contact: abuabdullah.be@outlook.com
# =============================================================================
"""
license.py  --  Net-monit V10.7 Licensing Engine

IMPORTANT: _SIGN_SECRET below MUST match $SIGN_SECRET in LicenseKeyGenerator.ps1
           and LicenseKeyGenerator.py exactly. Both use:
             "NM55@Abdullah_InfoXtek_2025"

Key format: XXXXX-XXXXX  (11 chars including dash, base-36 alphanumeric)
Algorithm:
  1. payload  = UPPER(device_id) + ":" + UPPER(activation_code)
  2. km       = HMAC-SHA256(payload.encode('utf-8'), SECRET.encode('utf-8'))
  3. n1       = big-endian uint32 from km[0:4]
  4. n2       = big-endian uint32 from km[4:8]
  5. part1    = base36(n1 % 36^5).zfill(5)
  6. part2    = base36(n2 % 36^5).zfill(5)
  7. key      = part1 + "-" + part2

Trial: 30 days. After expiry without a valid key: restricted mode.
"""

import hashlib, hmac, os, platform, socket, time, uuid, json, logging, re, struct

log = logging.getLogger("netmonit.license")

# ============================================================
# CANONICAL SIGNING SECRET
# Must be identical in:
#   monitor/license.py          (this file)
#   setup/LicenseKeyGenerator.ps1
#   setup/LicenseKeyGenerator.py
# ============================================================
_SIGN_SECRET = b"NM55@Abdullah_InfoXtek_2025"

_B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

STATE_VALID   = "valid"
STATE_TRIAL   = "trial"
STATE_EXPIRED = "expired"
STATE_INVALID = "invalid"


# ============================================================
# DEVICE FINGERPRINTING
# ============================================================

def _safe(fn, default=""):
    try:
        return str(fn())
    except Exception:
        return default


def _get_mac():
    mac_int = uuid.getnode()
    if (mac_int >> 40) & 1:
        return "000000000000"
    return "%012x" % mac_int


def _get_cpu_id():
    if platform.system() == "Windows":
        try:
            import subprocess
            out = subprocess.check_output(
                ["wmic", "cpu", "get", "ProcessorId"], timeout=4
            ).decode(errors="ignore")
            for line in out.splitlines():
                line = line.strip()
                if line and line != "ProcessorId":
                    return line
        except Exception:
            pass
    if platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "Serial" in line or "Hardware" in line:
                        return line.split(":")[-1].strip()
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":")[-1].strip()
        except Exception:
            pass
    return platform.processor() or "unknown-cpu"


def get_device_id() -> str:
    """16-char uppercase hex. Stable: hostname + MAC + OS + CPU."""
    parts = [
        _safe(socket.gethostname),
        _get_mac(),
        platform.system(),
        platform.machine(),
        _get_cpu_id(),
    ]
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest().upper()[:16]


def get_activation_code() -> str:
    """16-char uppercase hex. Stable: Python version + install path + node UUID."""
    install_path = _safe(lambda: os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    ))
    parts = [
        platform.python_version(),
        install_path,
        str(uuid.UUID(int=uuid.getnode())),
        platform.node(),
    ]
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest().upper()[:16]


# ============================================================
# KEY ALGORITHM  (identical in PS1 and Python generator)
# ============================================================

def _to_b36(n: int, width: int) -> str:
    if n == 0:
        return "0" * width
    chars = []
    while n:
        chars.append(_B36[n % 36])
        n //= 36
    return ("".join(reversed(chars))).zfill(width)


def _derive_km(device_id: str, activation_code: str) -> bytes:
    """HMAC-SHA256(UPPER(device_id):UPPER(activation_code), _SIGN_SECRET)"""
    payload = f"{device_id.upper()}:{activation_code.upper()}".encode("utf-8")
    return hmac.new(_SIGN_SECRET, payload, hashlib.sha256).digest()


def generate_license_key(device_id: str, activation_code: str) -> str:
    km   = _derive_km(device_id, activation_code)
    n1   = struct.unpack(">I", km[0:4])[0]
    n2   = struct.unpack(">I", km[4:8])[0]
    mod  = 36 ** 5
    p1   = _to_b36(n1 % mod, 5)
    p2   = _to_b36(n2 % mod, 5)
    return f"{p1}-{p2}"


def validate_license_key(key: str, device_id: str, activation_code: str) -> bool:
    key = key.strip().upper().replace(" ", "")
    if not re.match(r"^[0-9A-Z]{5}-[0-9A-Z]{5}$", key):
        return False
    expected = generate_license_key(device_id, activation_code)
    return hmac.compare_digest(key, expected)


# ============================================================
# LICENSE MANAGER
# ============================================================

TRIAL_DAYS = 30


class LicenseManager:
    def __init__(self):
        self._state           = None
        self._record          = None
        self._device_id       = None
        self._activation_code = None

    def _load(self):
        from . import database as db
        self._device_id       = get_device_id()
        self._activation_code = get_activation_code()
        self._record          = db.get_license_record()

        if self._record is None:
            db.set_license_record(
                device_id       = self._device_id,
                activation_code = self._activation_code,
                license_key     = "",
                trial_start     = time.time(),
                activated       = 0,
            )
            self._record = db.get_license_record()

        self._state = self._compute_state()
        log.info("License state: %s  device_id=%s", self._state, self._device_id)
        return self._state

    def _compute_state(self) -> str:
        r = self._record
        if r.get("activated"):
            if validate_license_key(
                r.get("license_key", ""),
                self._device_id,
                self._activation_code,
            ):
                return STATE_VALID
            return STATE_INVALID
        trial_start  = r.get("trial_start", time.time())
        elapsed_days = (time.time() - trial_start) / 86400
        return STATE_TRIAL if elapsed_days <= TRIAL_DAYS else STATE_EXPIRED

    def refresh(self):
        self._load()

    @property
    def state(self) -> str:
        if self._state is None:
            self._load()
        return self._state

    @property
    def device_id(self) -> str:
        if self._device_id is None:
            self._load()
        return self._device_id

    @property
    def activation_code(self) -> str:
        if self._activation_code is None:
            self._load()
        return self._activation_code

    @property
    def trial_days_remaining(self) -> int:
        if self._record is None:
            self._load()
        ts      = self._record.get("trial_start", time.time())
        elapsed = (time.time() - ts) / 86400
        return max(0, int(TRIAL_DAYS - elapsed))

    @property
    def trial_start_date(self) -> str:
        if self._record is None:
            self._load()
        import datetime
        return datetime.datetime.fromtimestamp(
            self._record.get("trial_start", time.time())
        ).strftime("%Y-%m-%d")

    @property
    def is_full_access(self) -> bool:
        return self.state in (STATE_VALID, STATE_TRIAL)

    @property
    def is_restricted(self) -> bool:
        return self.state in (STATE_EXPIRED, STATE_INVALID)

    def activate(self, license_key: str) -> dict:
        from . import database as db
        self._device_id       = get_device_id()
        self._activation_code = get_activation_code()
        if validate_license_key(license_key, self._device_id, self._activation_code):
            db.set_license_activated(license_key.strip().upper())
            self._record = db.get_license_record()
            self._state  = STATE_VALID
            log.info("License activated: %s", license_key)
            return {"ok": True, "message": "License activated successfully. Full access granted."}
        log.warning("Invalid key attempt: %s", license_key)
        return {"ok": False, "message": "Invalid license key. Please check the key and try again."}

    def get_status_dict(self) -> dict:
        return {
            "state":                self.state,
            "device_id":            self.device_id,
            "activation_code":      self.activation_code,
            "trial_days_remaining": self.trial_days_remaining,
            "trial_start":          self.trial_start_date,
            "is_full_access":       self.is_full_access,
            "is_restricted":        self.is_restricted,
            "trial_total_days":     TRIAL_DAYS,
        }


license_manager = LicenseManager()
