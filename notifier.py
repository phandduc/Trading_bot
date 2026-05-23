import urllib.request
import json
import config
import ssl



def send_telegram_message(text):
    """Gửi tin nhắn HTML tới Telegram channel/chat."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("Lỗi: Chưa cấu hình Telegram Bot Token hoặc Chat ID trong file .env")
        return False
        
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        # Bỏ qua xác thực SSL để tránh lỗi CERTIFICATE_VERIFY_FAILED
        context = ssl._create_unverified_context()
        # Sử dụng urllib (thư viện chuẩn của Python) để không cần cài đặt requests
        with urllib.request.urlopen(req, timeout=10, context=context) as response:
            res_body = json.loads(response.read().decode('utf-8'))
            if res_body.get('ok'):
                print("Đã gửi tin nhắn Telegram thành công.")
                return True
            else:
                print(f"Gửi tin nhắn Telegram thất bại: {res_body}")
                return False
    except Exception as e:
        print(f"Lỗi kết nối API Telegram: {e}")
        return False

def format_price(price, symbol):
    """Định dạng giá động theo loại tài sản (5 chữ số cho FX, 2 chữ số cho Vàng)."""
    symbol_display = symbol.upper()
    dec = 5 if 'USD' in symbol_display and 'XAU' not in symbol_display else 2
    return f"{price:.{dec}f}"

def format_signal_message(signal):
    """Định dạng tín hiệu thành tin nhắn HTML đẹp mắt."""
    action_emoji = "🟢 <b>BUY (MUA)</b>" if signal['action'] == 'BUY' else "🔴 <b>SELL (BÁN)</b>"
    
    confluences_str = "\n".join([f"- {c}" for c in signal['confluences']])
    
    symbol_display = signal.get('symbol', 'XAUUSD').upper()
    
    # Dòng thông báo trạng thái đặt lệnh tự động
    auto_trade_status = ""
    if signal.get('executed'):
        auto_trade_status = (
            f"🤖 <b>Tự động đặt lệnh:</b> THÀNH CÔNG\n"
            f"📦 <b>Khối lượng:</b> {signal.get('volume'):.2f} Lot\n"
            f"🎟️ <b>Mã lệnh (Ticket):</b> #{signal.get('ticket')}\n\n"
        )
    elif config.AUTO_TRADE:
        auto_trade_status = f"🤖 <b>Tự động đặt lệnh:</b> THẤT BẠI ({signal.get('err_desc', 'Lỗi không xác định')})\n\n"
    else:
        auto_trade_status = f"🤖 <b>Tự động đặt lệnh:</b> Chế độ chỉ báo tín hiệu\n\n"
    
    message = (
        f"🚨 <b>TÍN HIỆU GIAO DỊCH {symbol_display}</b> 🚨\n\n"
        f"⚡ <b>Hành động:</b> {action_emoji}\n"
        f"🕒 <b>Thời gian quét:</b> {signal['time']}\n"
        f"⏱ <b>Thời gian biểu đồ:</b> M15 & H1 (Đồng bộ)\n\n"
        f"🎯 <b>Giá vào lệnh (Entry):</b> {format_price(signal['entry'], symbol_display)}\n"
        f"🛑 <b>Cắt lỗ (SL):</b> {format_price(signal['sl'], symbol_display)}\n"
        f"💰 <b>Chốt lời (TP):</b> {format_price(signal['tp'], symbol_display)}\n"
        f"⚖️ <b>Tỷ lệ R:R:</b> {signal['rr']:.2f}\n\n"
        f"{auto_trade_status}"
        f"🔍 <b>Yếu tố hợp lưu (Confluence):</b>\n{confluences_str}\n\n"
        f"📐 <b>Vùng Fibonacci M15:</b>\n"
        f"- Fibo 0.5: {format_price(signal['fib_levels']['0.5'], symbol_display)}\n"
        f"- Fibo 0.618: {format_price(signal['fib_levels']['0.618'], symbol_display)}\n"
        f"- Fibo 0.786: {format_price(signal['fib_levels']['0.786'], symbol_display)}\n\n"
        f"<i>*Lưu ý: Luôn tuân thủ quản lý vốn!</i>"
    )
    return message

def send_signal_notification(signal):
    """Hàm wrapper định dạng và gửi tín hiệu."""
    msg = format_signal_message(signal)
    return send_telegram_message(msg)

def send_break_even_notification(symbol, ticket, entry_price):
    """Gửi thông báo dời Stop Loss về hòa vốn (Break-Even)."""
    symbol_display = symbol.upper()
    msg = (
        f"🛡️ <b>BẢO VỆ VỊ THẾ {symbol_display}</b> 🛡️\n\n"
        f"📈 Lệnh <b>#{ticket}</b> đã đi đúng hướng đạt tỷ lệ <b>1:1 R:R</b>.\n"
        f"Entry: {format_price(entry_price, symbol_display)}\n"
        f"👉 <b>Đã dời Stop Loss về điểm Entry (Hòa vốn - Break-Even) để bảo toàn vốn!</b>"
    )
    return send_telegram_message(msg)

def send_partial_tp_notification(symbol, ticket, partial_lot, price):
    """Gửi thông báo chốt lời từng phần 50% khối lượng (Partial Take Profit)."""
    symbol_display = symbol.upper()
    msg = (
        f"💰 <b>CHỐT LỜI TỪNG PHẦN (PARTIAL TP) {symbol_display}</b> 💰\n\n"
        f"📈 Lệnh <b>#{ticket}</b> đã đi đúng hướng đạt tỷ lệ <b>1:1.5 R:R</b>.\n"
        f"🔥 <b>Đã chốt lời 50% khối lượng:</b> {partial_lot:.2f} Lot tại giá {format_price(price, symbol_display)}\n"
        f"👉 Còn lại 50% khối lượng tiếp tục gồng về TP chính H1."
    )
    return send_telegram_message(msg)

def send_trailing_stop_notification(symbol, ticket, new_sl):
    """Gửi thông báo dời Stop Loss theo cấu trúc (Trailing Stop)."""
    symbol_display = symbol.upper()
    msg = (
        f"🏃‍♂️ <b>TRAILING STOP {symbol_display}</b> 🏃‍♂️\n\n"
        f"📈 Lệnh <b>#{ticket}</b> (50% khối lượng còn lại) đã được dời SL theo cấu trúc đỉnh/đáy M15 mới.\n"
        f"👉 <b>Mức Stop Loss mới:</b> {format_price(new_sl, symbol_display)}"
    )
    return send_telegram_message(msg)

def send_execution_error_notification(symbol, action, error_msg):
    """Gửi thông báo lỗi khi không thể tự động đặt lệnh."""
    symbol_display = symbol.upper()
    msg = (
        f"⚠️ <b>LỖI VÀO LỆNH TỰ ĐỘNG {symbol_display}</b> ⚠️\n\n"
        f"Hành động: {action}\n"
        f"Lý do thất bại: <code>{error_msg}</code>\n"
        f"Vui lòng kiểm tra ứng dụng MT5 của bạn!"
    )
    return send_telegram_message(msg)



# Để test nhanh Telegram
if __name__ == "__main__":
    test_msg = "🔌 <b>Telegram Bot XAU/USD</b> đã kết nối thành công và đang hoạt động!"
    send_telegram_message(test_msg)

