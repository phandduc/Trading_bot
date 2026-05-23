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

# Tham số kỹ thuật & Đa tài sản
SYMBOLS_STR = os.environ.get("SYMBOLS", "XAUUSD,EURUSD,GBPUSD")
SYMBOLS = [s.strip() for s in SYMBOLS_STR.split(",") if s.strip()]

# Cấu hình giao dịch tự động
AUTO_TRADE = os.environ.get("AUTO_TRADE", "false").lower() == "true"
try:
    RISK_PERCENT = float(os.environ.get("RISK_PERCENT", "1.0"))
except ValueError:
    RISK_PERCENT = 1.0

MAGIC_NUMBER = 20260520

# Vẫn giữ SYMBOL mặc định làm fallback
SYMBOL = SYMBOLS[0] if SYMBOLS else "XAUUSD"

# Tham số cấu hình rủi ro & quản lý vốn tối ưu
FIB_LEVELS = [0.5, 0.618, 0.786]
MIN_RR_RATIO = 1.5

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


