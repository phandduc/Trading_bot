import data_provider
import strategy
import notifier
import config
from datetime import datetime

def test_single_scan():
    print("="*60)
    print(" BẮT ĐẦU KIỂM TRA MỘT LƯỢT QUÉT THỊ TRƯỜNG ")
    print("="*60)
    
    # 1. Khởi tạo MT5
    if not data_provider.initialize_mt5():
        print("Lỗi: Không thể kết nối tới MetaTrader 5.")
        return
        
    try:
        # 2. Lấy ký hiệu thực tế
        actual_sym = data_provider.get_actual_symbol(config.SYMBOL)
        print(f"Ký hiệu thực tế được sử dụng: {actual_sym}")
        
        # 3. Lấy dữ liệu
        print("Đang lấy dữ liệu nến H1...")
        df_h1 = data_provider.get_rates(actual_sym, 'H1', 300)
        print("Đang lấy dữ liệu nến M15...")
        df_m15 = data_provider.get_rates(actual_sym, 'M15', 300)
        
        if df_h1 is None or df_m15 is None:
            print("Lỗi: Không thể tải dữ liệu nến từ MT5.")
            return
            
        print(f"Đã tải {len(df_h1)} nến H1 và {len(df_m15)} nến M15 thành công.")
        
        # 4. Chạy phân tích chiến lược
        print("\n--- Đang phân tích kỹ thuật và chiến lược ---")
        import MetaTrader5 as mt5
        sym_info = mt5.symbol_info(actual_sym)
        current_spread = sym_info.spread if sym_info is not None else 0.0
        signal, skip_reason = strategy.analyze_market(actual_sym, df_h1, df_m15, current_spread=current_spread)
        
        if signal is not None:
            print("\n🚀 PHÁT HIỆN TÍN HIỆU GIAO DỊCH:")
            print(f"- Hành động: {signal['action']}")
            print(f"- Entry: {signal['entry']:.2f}")
            print(f"- SL: {signal['sl']:.2f}")
            print(f"- TP: {signal['tp']:.2f}")
            print(f"- Tỷ lệ RR: {signal['rr']:.2f}")
            print(f"- Hợp lưu: {signal['confluences']}")
            
            # Gửi tin nhắn test lên Telegram
            print("Đang gửi tín hiệu lên Telegram...")
            notifier.send_signal_notification(signal)
        else:
            print(f"\nKhông phát hiện tín hiệu giao dịch hợp lệ tại lượt quét này: {skip_reason}")
            
    except Exception as e:
        print(f"Lỗi trong quá trình kiểm tra: {e}")
    finally:
        # 5. Đóng MT5
        data_provider.shutdown_mt5()
        print("="*60)

if __name__ == "__main__":
    test_single_scan()
