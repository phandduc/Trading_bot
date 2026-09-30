#  XAUUSD Trading Bot (MT5 + Telegram)

Bot giao dịch tự động Vàng (**XAUUSD**) trên **MetaTrader 5** theo phương pháp **Smart Money Concepts (SMC) / Price Action**, hỗ trợ phát tín hiệu và quản lý lệnh nâng cao qua **Telegram**.

**Lưu ý trước khi đọc:** Bot vẫn đang quá trình phát triển và tối ưu hệ thống. Dưới đây sẽ sử dụng các từ ngữ chuyên ngành. Yêu cầu tìm hiểu phương pháp SMC/PA; chỉ báo Fibonacci, ATR trước khi tiếp tục. 
>  **Cảnh báo rủi ro:** _Dự án phục vụ mục đích học tập và nghiên cứu không nhằm mục đích thương mại, **miễn trừ trách nhiệm đối với mọi vấn đề phát sinh trong quá trình sử dụng**_.

_Giao dịch GOLD CFD có đòn bẩy cao và rủi ro lớn. Hãy thử nghiệm kỹ trên tài khoản **Demo** trước khi giao dịch thực tế._

---

##  Tính năng nổi bật & Logic cải tiến

1. **Chống Repainting / Look-Ahead Bias:**
   - Phân tích kỹ thuật, FVG, Order Block, Fibonacci và nến xác nhận hoàn toàn dựa trên nến M15 **đã đóng cửa (`iloc[-2]`)**, giúp kết quả Backtest khớp chính xác với Live Trading.

2. **Đồng bộ SL theo cấu trúc M15:**
   - **BUY:** `SL = min(Đáy Order Block M15, Swing Low M15 gần nhất) - (0.5 × ATR_M15)`
   - **SELL:** `SL = max(Đỉnh Order Block M15, Swing High M15 gần nhất) + (0.5 × ATR_M15)`
   - Thu hẹp khoảng cách rủi ro, tối ưu tỷ lệ Risk:Reward ($RR \ge 1.4$).

3. **Take Profit (TP) động & Fibonacci Extension:**
   - TP chính dựa trên đỉnh/đáy H1 kế tiếp.
   - Khi giá phá đỉnh/đáy lịch sử H1, bot tự động tính TP theo **Fibonacci Extension 1.272** của sóng M15 gần nhất hoặc biến động **`2.0 × ATR_H1`**.

4. **Bộ lọc Spread thời gian thực:**
   - Kiểm tra spread trước mỗi lệnh quét (`MAX_ALLOWED_SPREAD`). Tự động bỏ qua tín hiệu nếu spread dãn mạnh (chuyển phiên / ra tin tức).

5. **Quản lý vị thế nâng cao:**
   - **Break-Even (BE):** Dời SL về hòa vốn khi đạt **0.8 RR**.
   - **Partial TP:** Chốt lời **50% khối lượng** tại **1.5 RR**.
   - **Trailing Stop:** Dời SL cho 50% khối lượng còn lại theo cấu trúc Swing M15 mới.

6. **Bảo vệ tài khoản & An toàn:**
   - Giới hạn lỗ tối đa trong ngày (`MAX_DAILY_DRAWDOWN_PCT`).
   - Giới hạn chuỗi thua liên tiếp (`MAX_CONSECUTIVE_LOSSES`).
   - Giới hạn số lệnh mở đồng thời (`MAX_OPEN_POSITIONS`).

---

##  Cấu trúc dự án

```
.
├── main.py              # Vòng lặp chính: quét tín hiệu XAUUSD, đặt lệnh, quản lý vị thế đang chạy
├── strategy.py          # Logic phân tích SMC/Price Action, SL/TP, FVG/OB, Fibonacci
├── indicators.py        # Tính Swing High/Low, Trend H1/M15, Fibonacci, FVG, Order Block, ATR
├── data_provider.py     # Kết nối MetaTrader 5 và tải dữ liệu nến
├── notifier.py          # Định dạng và gửi thông báo Telegram (Signal, BE, Partial TP, Trailing)
├── config.py            # Quản lý tham số cấu hình, profile rủi ro, môi trường .env
├── backtest.py          # Chạy mô phỏng lịch sử, báo cáo theo tháng, Walk-Forward OOS
├── test_scan.py         # Kiểm tra thử 1 lượt quét tín hiệu XAUUSD
├── test_telegram.py     # Kiểm tra kết nối Telegram Bot
├── run_bot.bat          # File chạy bot nhanh trên Windows
├── run_backtest.bat     # File chạy backtest nhanh trên Windows
└── .env                 # Cấu hình cá nhân (KHÔNG commit)
```

---

##  Cài đặt & Cấu hình

### 1. Yêu cầu hệ thống
- **Windows OS** (thư viện `MetaTrader5` yêu cầu Windows)
- **Python 3.10+** (khuyến nghị 3.12)
- **MetaTrader 5** đã cài đặt, đăng nhập tài khoản và bật **Algo Trading**.

### 2. Cài đặt thư viện
```bash
pip install MetaTrader5 pandas numpy matplotlib
```

### 3. Cấu hình file `.env`
Tạo file `.env` ở thư mục gốc dự án:

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# MT5 (bỏ trống nếu MT5 đã đăng nhập sẵn)
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=Your-Broker-Server

# Thiết lập giao dịch
AUTO_TRADE=false          # true: tự đặt lệnh | false: chỉ báo tín hiệu Telegram
RISK_PERCENT=1.0          # % rủi ro trên mỗi lệnh
SYMBOLS=XAUUSD

# Giờ giao dịch (Giờ Việt Nam UTC+7)
SESSION_START_HOUR=13
SESSION_END_HOUR=23
```

---

##  Tham số & Profiles

Bot hỗ trợ 4 Trade Profiles linh hoạt:

| Tham số | Ý nghĩa | Mặc định (`balanced`) |
|---|---|---|
| `TRADE_PROFILE` | Cấu hình profile | `balanced` (`conservative` / `balanced` / `active` / `sureshot`) |
| `MIN_RR_RATIO` | Tỷ lệ R:R tối thiểu | `1.4` |
| `MAX_ALLOWED_SPREAD` | Threshold spread tối đa (points) | `30.0` |
| `MAX_RISK_ATR_MULT` | Ngưỡng SL/ATR H1 tối đa | `3.0` |
| `MIN_RISK_ATR_MULT` | Ngưỡng SL/ATR H1 tối thiểu | `0.45` |
| `ATR_SPIKE_FILTER_MULT` | Lọc tin tức biến động | `2.0` |
| `ALLOW_FRIDAY_TRADING` | Cho phép giao dịch Thứ 6 | `true` |

---

##  Sử dụng

### 1. Khởi chạy Bot Live Trading
```bash
python main.py
```
Hoặc double-click `run_bot.bat`.

### 2. Quét thử 1 lượt tín hiệu hiện tại
```bash
python test_scan.py
```

### 3. Test gửi tin nhắn Telegram
```bash
python test_telegram.py
```

### 4. Chạy Backtest lịch sử
```bash
# Backtest XAUUSD trong 45 ngày gần nhất
python backtest.py XAUUSD 45
```
Hoặc double-click `run_backtest.bat`.

---

##  Cơ chế quản lý lệnh tự động

- **Khi mở lệnh:** Lưu thông tin ticket và giá entry vào `position_state.json`.
- **Đạt 0.8 RR:** Bot dời Stop Loss về đúng giá **Entry (Break-Even)** để bảo toàn vốn.
- **Đạt 1.5 RR:** Bot tự động chốt **50% khối lượng** (Partial TP) và gửi thông báo Telegram.
- **Sau khi Partial TP:** 50% khối lượng còn lại kích hoạt **Trailing Stop** dời SL theo đỉnh/đáy M15 mới hình thành.

---

##  Giấy phép & Tác giả

- **Tác giả:** phandduc
- **Dự án:** XAUUSD SMC Trading Bot
- **Giấy phép:** Chưa chỉ định. Bạn có thể thêm file `LICENSE` (ví dụ MIT) tùy nhu cầu.
