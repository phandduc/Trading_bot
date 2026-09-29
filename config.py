import os
from pathlib import Path

# Thư mục gốc dự án
BASE_DIR = Path(__file__).resolve().parent

# Hàm tự đọc file .env không phụ thuộc thư viện ngoài
def load_env(env_path=BASE_DIR / ".env"):
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()

load_env()

# Cấu hình Telegram
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Cấu hình MT5
MT5_LOGIN = os.environ.get("MT5_LOGIN", "")
MT5_PASSWORD = os.environ.get("MT5_PASSWORD", "")
MT5_SERVER = os.environ.get("MT5_SERVER", "")

# Chi tiết tài khoản đăng nhập nếu có
if MT5_LOGIN:
    try:
        MT5_LOGIN = int(MT5_LOGIN)
    except ValueError:
        MT5_LOGIN = None

# Tham số kỹ thuật & Danh sách tài sản (Mặc định XAUUSD)
SYMBOLS_STR = os.environ.get("SYMBOLS", "XAUUSD")
SYMBOLS = [s.strip() for s in SYMBOLS_STR.split(",") if s.strip()]

# Cấu hình giao dịch tự động
AUTO_TRADE = os.environ.get("AUTO_TRADE", "false").lower() == "true"
try:
    RISK_PERCENT = float(os.environ.get("RISK_PERCENT", "1.0"))
except ValueError:
    RISK_PERCENT = 1.0

MAGIC_NUMBER = 20260520

# SYMBOL mặc định
SYMBOL = SYMBOLS[0] if SYMBOLS else "XAUUSD"

# Tham số cấu hình rủi ro & quản lý vốn tối ưu
FIB_LEVELS = [0.5, 0.618, 0.786]
TRADE_PROFILE = os.environ.get("TRADE_PROFILE", "balanced").strip().lower()
if TRADE_PROFILE not in {"conservative", "balanced", "active", "sureshot"}:
    TRADE_PROFILE = "balanced"

PROFILE_DEFAULTS = {
    "conservative": {
        "MIN_RR_RATIO": 1.5,
        "MAX_RR_RATIO": 1.9,
        "MAX_RISK_ATR_MULT": 2.5,
        "MIN_RISK_ATR_MULT": 0.6,
        "ATR_SPIKE_FILTER_MULT": 1.6,
        "M15_CONFIRM_MODE": "wick",
        "FIB_ENTRY_LOWER": 0.618,
        "ALLOW_FRIDAY_TRADING": False,
        "MIN_CONFLUENCE_SCORE": 2,
        "TREND_MIN_STEP_ATR": 0.40,
    },
    "balanced": {
        "MIN_RR_RATIO": 1.4,
        "MAX_RR_RATIO": 1.9,
        "MAX_RISK_ATR_MULT": 3.0,
        "MIN_RISK_ATR_MULT": 0.45,
        "ATR_SPIKE_FILTER_MULT": 2.0,
        "M15_CONFIRM_MODE": "none",
        "FIB_ENTRY_LOWER": 0.5,
        "ALLOW_FRIDAY_TRADING": True,
        "MIN_CONFLUENCE_SCORE": 1,
        "TREND_MIN_STEP_ATR": 0.15,
    },
    "active": {
        "MIN_RR_RATIO": 1.3,
        "MAX_RR_RATIO": 3.2,
        "MAX_RISK_ATR_MULT": 3.5,
        "MIN_RISK_ATR_MULT": 0.35,
        "ATR_SPIKE_FILTER_MULT": 2.4,
        "M15_CONFIRM_MODE": "none",
        "FIB_ENTRY_LOWER": 0.5,
        "ALLOW_FRIDAY_TRADING": True,
        "MIN_CONFLUENCE_SCORE": 1,
        "TREND_MIN_STEP_ATR": 0.20,
    },
    "sureshot": {
        "MIN_RR_RATIO": 1.4,
        "MAX_RR_RATIO": 1.9,
        "MAX_RISK_ATR_MULT": 3.0,
        "MIN_RISK_ATR_MULT": 0.45,
        "ATR_SPIKE_FILTER_MULT": 2.0,
        "M15_CONFIRM_MODE": "none",
        "FIB_ENTRY_LOWER": 0.5,
        "ALLOW_FRIDAY_TRADING": True,
        "MIN_CONFLUENCE_SCORE": 1,
        "TREND_MIN_STEP_ATR": 0.15,
    },
}

_pf = PROFILE_DEFAULTS[TRADE_PROFILE]

def _env_float(name, default):
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return float(default)

def _env_bool(name, default):
    val = os.environ.get(name, str(default)).strip().lower()
    if val in {"1", "true", "yes", "on"}:
        return True
    if val in {"0", "false", "no", "off"}:
        return False
    return bool(default)

MIN_RR_RATIO = _env_float("MIN_RR_RATIO", _pf["MIN_RR_RATIO"])
MAX_RR_RATIO = _env_float("MAX_RR_RATIO", _pf["MAX_RR_RATIO"])
MAX_RISK_ATR_MULT = _env_float("MAX_RISK_ATR_MULT", _pf["MAX_RISK_ATR_MULT"])
MIN_RISK_ATR_MULT = _env_float("MIN_RISK_ATR_MULT", _pf["MIN_RISK_ATR_MULT"])
ATR_SPIKE_FILTER_MULT = _env_float("ATR_SPIKE_FILTER_MULT", _pf["ATR_SPIKE_FILTER_MULT"])
FIB_ENTRY_LOWER = _env_float("FIB_ENTRY_LOWER", _pf["FIB_ENTRY_LOWER"])
if FIB_ENTRY_LOWER < 0.5:
    FIB_ENTRY_LOWER = 0.5
if FIB_ENTRY_LOWER not in {0.5, 0.618}:
    FIB_ENTRY_LOWER = 0.5
ALLOW_FRIDAY_TRADING = _env_bool("ALLOW_FRIDAY_TRADING", _pf["ALLOW_FRIDAY_TRADING"])

M15_CONFIRM_MODE = os.environ.get("M15_CONFIRM_MODE", _pf["M15_CONFIRM_MODE"]).strip().lower()
if M15_CONFIRM_MODE not in {"none", "body", "wick"}:
    M15_CONFIRM_MODE = _pf["M15_CONFIRM_MODE"]

ENABLE_QUALITY_RISK_SCALING = _env_bool("ENABLE_QUALITY_RISK_SCALING", True)
LOW_QUALITY_RISK_MULT = _env_float("LOW_QUALITY_RISK_MULT", 0.65)
MIN_CONFLUENCE_SCORE = int(_env_float("MIN_CONFLUENCE_SCORE", _pf["MIN_CONFLUENCE_SCORE"]))
TREND_MIN_STEP_ATR = _env_float("TREND_MIN_STEP_ATR", _pf["TREND_MIN_STEP_ATR"])
MAX_ALLOWED_SPREAD = _env_float("MAX_ALLOWED_SPREAD", 30.0)

# Thiết lập giới hạn tự động dừng (Circuit Breaker & Cooldown)
try:
    MAX_DAILY_DRAWDOWN_PCT = float(os.environ.get("MAX_DAILY_DRAWDOWN_PCT", "4.0"))
    MAX_CONSECUTIVE_LOSSES = int(os.environ.get("MAX_CONSECUTIVE_LOSSES", "3"))
    MAX_OPEN_POSITIONS = int(os.environ.get("MAX_OPEN_POSITIONS", "2"))
except ValueError:
    MAX_DAILY_DRAWDOWN_PCT = 4.0
    MAX_CONSECUTIVE_LOSSES = 3
    MAX_OPEN_POSITIONS = 2

# Cấu hình giờ giao dịch
try:
    SESSION_START_HOUR = int(os.environ.get("SESSION_START_HOUR", "13"))
    SESSION_END_HOUR = int(os.environ.get("SESSION_END_HOUR", "23"))
except ValueError:
    SESSION_START_HOUR = 13
    SESSION_END_HOUR = 23

print("Đã tải cấu hình bot thành công.")
print(f"- Che do tu dong dat lenh: {AUTO_TRADE} (Rui ro: {RISK_PERCENT}%)")
print(f"- Danh sach ma quet: {SYMBOLS}")
print(f"- Gio giao dich (Viet Nam - UTC+7): {SESSION_START_HOUR}h - {SESSION_END_HOUR}h")
print(f"- Trade profile: {TRADE_PROFILE}")
print(f"- Bo loc chat luong: RR [{MIN_RR_RATIO}, {MAX_RR_RATIO}], SL/ATR [{MIN_RISK_ATR_MULT}, {MAX_RISK_ATR_MULT}], ATR spike x{ATR_SPIKE_FILTER_MULT}, M15 confirm={M15_CONFIRM_MODE}")
print(f"- Entry pullback: Fibonacci [{FIB_ENTRY_LOWER} - 0.786], Thu 6 duoc phep: {ALLOW_FRIDAY_TRADING}")
print(f"- Spread toi da cho phep: {MAX_ALLOWED_SPREAD} points")
print(f"- Risk scaling theo chat luong: {ENABLE_QUALITY_RISK_SCALING} (low quality x{LOW_QUALITY_RISK_MULT})")
print(f"- Filter cau truc: min confluence={MIN_CONFLUENCE_SCORE}, trend step min={TREND_MIN_STEP_ATR} ATR")
