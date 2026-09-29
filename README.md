#  XAUUSD / GBPUSD Trading Bot (MT5 + Telegram)

Bot giao dịch tự động trên **MetaTrader 5** theo phương pháp **Smart Money Concepts (SMC) / Price Action**, hỗ trợ đa tài sản (mặc định `XAUUSD`, `GBPUSD`), gửi tín hiệu và cập nhật trạng thái lệnh qua **Telegram**.

>  **Cảnh báo rủi ro:** Dự án phục vụ mục đích học tập và nghiên cứu. Giao dịch Forex/Gold CFD có đòn bẩy cao và có thể mất toàn bộ vốn. Kết quả backtest không đảm bảo kết quả tương lai. Hãy test kỹ trên tài khoản **Demo** trước khi dùng tiền thật. Tác giả không chịu trách nhiệm cho bất kỳ khoản lỗ nào.

---

##  Tính năng chính

- **Phân tích đa khung thời gian:** H1 xác định xu hướng, M15 tìm điểm vào lệnh.
- **Xu hướng thuần Price Action:** dựa trên cấu trúc đỉnh/đáy (HH/HL, LH/LL); tự loại Sideways khi cấu trúc bị phá vỡ (CHoCH/MSS).
- **Vùng vào lệnh Fibonacci:** pullback về vùng 0.5 / 0.618 – 0.786 của con sóng M15 gần nhất.
- **Hợp lưu (Confluence):** yêu cầu giá nằm trong vùng **FVG** (Fair Value Gap) và/hoặc **Order Block** chưa bị mitigate.
- **SL/TP theo cấu trúc H1:** SL tại Swing H1 gần nhất ± buffer `0.5 × ATR`, TP tại đỉnh/đáy H1 kế tiếp.
- **Bộ lọc chất lượng:** RR min/max, tỷ lệ SL/ATR, lọc ATR spike (tin tức), độ mạnh cấu trúc H1, xác nhận nến M15 (tùy chọn) và **lọc xác suất thắng** (rule-based scoring).
- **Quản lý lệnh nâng cao:**
  - Dời SL về hòa vốn (Break-Even) khi đạt **0.8 RR**.
  - Chốt lời từng phần **50% khối lượng** tại **1.5 RR**.
  - **Trailing Stop** theo swing M15 cho 50% còn lại.
- **Quản trị rủi ro & an toàn:** Circuit breaker (drawdown ngày, chuỗi thua liên tiếp, giới hạn số lệnh mở), kiểm tra spread trước khi vào lệnh, tự tính lot theo % rủi ro.
- **Thông báo Telegram:** tín hiệu, kết quả đặt lệnh, BE, Partial TP, Trailing Stop, cảnh báo lỗi/an toàn.
- **Backtest & Walk-forward:** mô phỏng nhiều chế độ TP, báo cáo theo tháng, xuất CSV, kiểm định ngoài mẫu (OOS).

---

##  Cấu trúc dự án

```
.
├── main.py              # Vòng lặp chính: quét tín hiệu, đặt lệnh, quản lý lệnh đang chạy
├── strategy.py          # Logic chiến lược (analyze_market) + chấm xác suất thắng
├── indicators.py        # Swing, xu hướng, Fibonacci, FVG, Order Block, ATR
├── data_provider.py     # Kết nối MT5 và lấy dữ liệu nến
├── notifier.py          # Gửi thông báo Telegram
├── config.py            # Đọc .env, cấu hình profile & tham số rủi ro
├── backtest.py          # Backtest, báo cáo theo tháng, walk-forward
├── test_scan.py         # Chạy thử 1 lượt quét thị trường
├── test_telegram.py     # Gửi tin nhắn thử tới Telegram
├── run_bot.bat          # Chạy bot (Windows)
├── run_backtest.bat     # Chạy backtest (Windows)
├── run_test_scan.bat    # Chạy test 1 lượt quét (Windows)
└── .env                 # Cấu hình cá nhân (KHÔNG commit)
```

---

##  Luồng hoạt động

```
Mỗi nến M15 mới
   │
   ├─ 1. Quản lý lệnh đang mở  → BE (0.8R) → Partial TP (1.5R) → Trailing Stop
   ├─ 2. Kiểm tra an toàn      → Drawdown ngày / Chuỗi thua / Số lệnh mở tối đa
   └─ 3. Quét từng symbol
         ├─ Lọc phiên & ngày giao dịch (giờ Việt Nam)
         ├─ Lọc ATR spike
         ├─ Xu hướng H1 (bỏ qua nếu Sideways / cấu trúc yếu)
         ├─ Giá nằm trong vùng Fibonacci pullback (M15)
         ├─ Hợp lưu FVG / Order Block
         ├─ (Tùy chọn) Xác nhận nến M15
         ├─ Tính SL / TP theo cấu trúc H1 → kiểm tra RR, SL/ATR
         ├─ Lọc xác suất thắng
         └─ Đặt lệnh (nếu AUTO_TRADE) + gửi Telegram
```

---

##  Yêu cầu

- **Windows** (thư viện `MetaTrader5` của Python chỉ hỗ trợ Windows)
- **Python 3.10+** (khuyến nghị 3.12)
- **MetaTrader 5** đã cài đặt, đã đăng nhập và bật *Algo Trading*
- Một **Telegram Bot** (tạo qua [@BotFather](https://t.me/BotFather)) và Chat ID của bạn

Thư viện Python:

```bash
pip install MetaTrader5 pandas numpy matplotlib
```

---

##  Cài đặt

1. **Clone repo**
   ```bash
   git clone https://github.com/phandduc/xauusd_trading_bot.git
   cd xauusd_trading_bot
   ```

2. **Cài thư viện**
   ```bash
   pip install MetaTrader5 pandas numpy matplotlib
   ```

3. **Tạo file `.env`** ở thư mục gốc (xem mẫu bên dưới).

4. **Sửa đường dẫn Python** trong các file `.bat` (`run_bot.bat`, `run_backtest.bat`, `run_test_scan.bat`) cho khớp máy của bạn, hoặc chạy trực tiếp bằng `python main.py`.

5. **Mở MetaTrader 5**, đăng nhập tài khoản và bật nút **Algo Trading**.

---

##  Cấu hình (`.env`)

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# MT5 (bỏ trống nếu MT5 đã đăng nhập sẵn trên máy)
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=Your-Broker-Server

# Giao dịch
AUTO_TRADE=false          # true = tự động đặt lệnh, false = chỉ báo tín hiệu
RISK_PERCENT=1.0          # % rủi ro trên mỗi lệnh
SYMBOLS=XAUUSD,GBPUSD

# Phiên giao dịch (giờ Việt Nam, UTC+7)
SESSION_START_HOUR=13
SESSION_END_HOUR=23
```

### Tham số tùy chọn

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `TRADE_PROFILE` | `balanced` | `conservative` / `balanced` / `active` / `sureshot` |
| `MIN_RR_RATIO`, `MAX_RR_RATIO` | theo profile | Khoảng RR chấp nhận |
| `MIN_RISK_ATR_MULT`, `MAX_RISK_ATR_MULT` | theo profile | Khoảng SL/ATR chấp nhận |
| `ATR_SPIKE_FILTER_MULT` | theo profile | Bỏ qua khi ATR vượt X lần trung bình |
| `M15_CONFIRM_MODE` | theo profile | `none` / `body` / `wick` |
| `FIB_ENTRY_LOWER` | theo profile | Cận trên vùng Fibo vào lệnh: `0.5` hoặc `0.618` |
| `ALLOW_FRIDAY_TRADING` | theo profile | Cho phép giao dịch thứ 6 |
| `MIN_WIN_PROB` | theo profile | Ngưỡng xác suất thắng tối thiểu |
| `SYMBOL_WIN_PROB_OVERRIDES` | theo profile | Ngưỡng riêng theo symbol, vd `XAUUSD:0.54,GBPUSD:0.62` |
| `MIN_CONFLUENCE_SCORE` | theo profile | Số hợp lưu tối thiểu (FVG/OB) |
| `TREND_MIN_STEP_ATR` | theo profile | Độ mạnh tối thiểu của cấu trúc H1 (đơn vị ATR) |
| `ENABLE_QUALITY_RISK_SCALING` | `true` | Giảm rủi ro với setup chất lượng thấp |
| `LOW_QUALITY_RISK_MULT` | `0.65` | Hệ số rủi ro cho setup chất lượng thấp |
| `MAX_DAILY_DRAWDOWN_PCT` | `4.0` | Dừng quét khi lỗ trong ngày vượt ngưỡng |
| `MAX_CONSECUTIVE_LOSSES` | `3` | Dừng quét khi thua liên tiếp |
| `MAX_OPEN_POSITIONS` | `2` | Số lệnh mở đồng thời tối đa |

### Các profile

| Profile | Đặc điểm |
|---|---|
| `conservative` | Ít lệnh, lọc chặt, có xác nhận nến M15, không giao dịch thứ 6 |
| `balanced` | Cân bằng giữa số lệnh và chất lượng (mặc định) |
| `active` | Nhiều lệnh hơn, ngưỡng lọc thoáng hơn |
| `sureshot` | Ngưỡng xác suất rất cao (0.90+), rất ít lệnh |

---

##  Sử dụng

### Chạy bot

```bash
python main.py
```

hoặc double-click `run_bot.bat`.

Bot sẽ gửi tin nhắn khởi động lên Telegram, sau đó quét thị trường mỗi khi có nến M15 mới.

>  **Khuyến nghị:** để `AUTO_TRADE=false` lúc đầu để chỉ nhận tín hiệu, quan sát một thời gian trước khi bật đặt lệnh tự động.

### Test một lượt quét

```bash
python test_scan.py
```

### Test kết nối Telegram

```bash
python test_telegram.py
```

### Backtest

```bash
# Tất cả symbol trong SYMBOLS, 45 ngày gần nhất
python backtest.py ALL 45

# Một symbol cụ thể, 90 ngày
python backtest.py XAUUSD 90
```

hoặc dùng `run_backtest.bat` để nhập tham số tương tác.

Kết quả gồm:
- Bảng hiệu suất theo tháng (số lệnh, winrate, TP/SL/BE, lợi nhuận tháng/lũy kế, drawdown tối đa)
- File CSV lịch sử lệnh: `backtest_report_<symbol>.csv`
- Kiểm định **Walk-Forward OOS** để đánh giá độ ổn định theo thời gian

Backtest lấy dữ liệu trực tiếp từ MT5, nên cần MT5 đang chạy và có đủ dữ liệu lịch sử.

---

##  Cơ chế an toàn

- **Giới hạn drawdown ngày:** tạm dừng quét tín hiệu mới khi lỗ trong ngày ≥ `MAX_DAILY_DRAWDOWN_PCT`.
- **Chuỗi thua liên tiếp:** dừng khi thua ≥ `MAX_CONSECUTIVE_LOSSES` lệnh gần nhất.
- **Giới hạn vị thế:** tối đa `MAX_OPEN_POSITIONS` lệnh mở, mỗi symbol chỉ 1 lệnh.
- **Kiểm tra spread:** bỏ qua nếu spread > 30% khoảng cách SL.
- **Lệnh đang chạy** vẫn được quản lý (BE / Partial TP / Trailing) kể cả khi bot tạm ngưng quét tín hiệu mới.
- Trạng thái lệnh được lưu trong `position_state.json` để không mất tiến trình khi khởi động lại.

---

##  Bảo mật

- File `.env` (chứa token Telegram và mật khẩu MT5) đã được `.gitignore` bỏ qua. **Không bao giờ commit file này.**
- Nếu lỡ để lộ token/mật khẩu, hãy thu hồi token qua @BotFather và đổi mật khẩu MT5 ngay.
- Nên dùng tài khoản MT5 **Demo** khi thử nghiệm.

##  Ghi chú kỹ thuật

- Dữ liệu thời gian của MT5 được coi là UTC và quy đổi sang giờ Việt Nam (UTC+7) khi lọc phiên giao dịch.
- Backtest dựng lại nến H1 đang hình thành từ các nến M15 đã đóng để tránh *look-ahead bias*.
- Khi một nến M15 chạm cả SL và TP, backtest xác định kết quả dựa trên khoảng cách từ giá mở cửa nến (dữ liệu OHLC không có tick nên đây chỉ là xấp xỉ).
- `MAGIC_NUMBER` mặc định là `20260520`, dùng để phân biệt lệnh của bot với lệnh thủ công.

---

##  Hướng phát triển

- [ ] Tối ưu tham số có kiểm định walk-forward
- [ ] Thêm tính toán spread/slippage/commission vào backtest
- [ ] Hỗ trợ thêm cặp tài sản khác

---

##  Giấy phép

Chưa chỉ định. Bạn có thể thêm file `LICENSE` (ví dụ MIT) tùy nhu cầu.

---

##  Tác giả

**phandduc** — [github.com/phandduc](https://github.com/phandduc)
