import os
import sys
import time
import MetaTrader5 as mt5

sys.path.append(r'C:\Users\Duc\.gemini\antigravity\scratch\xauusd_trading_bot')
import data_provider

def generate_sample_screenshot():
    print("=== DANG KHOI TAO MT5 DE CHUP ANH MAU CHAT ===")
    if not data_provider.initialize_mt5():
        print("Lỗi: Không thể kết nối Terminal MT5")
        return
        
    symbol = "XAUUSD"
    actual_sym = data_provider.get_actual_symbol(symbol)
    
    # 1. Mở biểu đồ M15 của XAUUSD
    print(f"Opening chart for {actual_sym} on M15...")
    chart_id = mt5.chart_open(actual_sym, mt5.TIMEFRAME_M15)
    if chart_id == 0 or chart_id is None:
        print("Không thể mở biểu đồ")
        mt5.shutdown()
        return
        
    # Đợi 2 giây để biểu đồ tải dữ liệu nến đầy đủ
    time.sleep(2.0)
    
    # Thiết lập một số thuộc tính hiển thị biểu đồ cho đẹp mắt
    # 0 = bars, 1 = candlesticks, 2 = line
    mt5.chart_set_integer(chart_id, mt5.CHART_MODE, mt5.CHART_CANDLES)
    mt5.chart_set_integer(chart_id, mt5.CHART_SHOW_GRID, True)
    mt5.chart_set_integer(chart_id, mt5.CHART_SHOW_TRADE_LEVELS, True)
    
    # 2. Chụp ảnh màn hình biểu đồ và lưu vào thư mục artifact
    artifact_dir = r"C:\Users\Duc\AppData\Local\Temp"  # Temporary fallback or workspace
    # Let's save directly to the artifact directory:
    dest_path = r"C:\Users\Duc\.gemini\antigravity\brain\641e3479-d98a-4ba2-a577-bc54bb3a849b\chart_sample.png"
    
    print(f"Saving screenshot to: {dest_path}")
    # Gọi hàm chụp ảnh biểu đồ của MT5
    success = mt5.chart_screen_shot(chart_id, dest_path, 1000, 600, mt5.ALIGN_RIGHT)
    
    if success:
        print("Chụp ảnh màn hình biểu đồ thành công!")
    else:
        print(f"Lỗi khi chụp ảnh màn hình: {mt5.last_error()}")
        
    # 3. Đóng biểu đồ
    mt5.chart_close(chart_id)
    mt5.shutdown()

if __name__ == '__main__':
    generate_sample_screenshot()
