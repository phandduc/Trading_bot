import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

import notifier

def test():
    print("Đang thử gửi tin nhắn test tới Telegram...")
    success = notifier.send_telegram_message(
        "🔔 <b>THỬ NGHIỆM KẾT NỐI</b>\n\n"
        "Chúc mừng! Bot giao dịch XAU/USD của bạn đã kết nối thành công tới Telegram của bạn.\n"
        "Sẵn sàng nhận tín hiệu giao dịch thực tế."
    )
    if success:
        print("Gửi tin nhắn thử nghiệm thành công! Vui lòng kiểm tra Telegram của bạn.")
    else:
        print("Gửi tin nhắn thử nghiệm thất bại. Vui lòng kiểm tra Token và Chat ID trong file .env.")

if __name__ == "__main__":
    test()
