import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
import config

def initialize_mt5():
    """Khởi tạo kết nối với phần mềm MetaTrader 5."""
    if not mt5.initialize():
        print(f"Khởi tạo MetaTrader 5 thất bại. Mã lỗi: {mt5.last_error()}")
        return False
    
    # Đăng nhập bằng tài khoản cụ thể nếu được cung cấp trong cấu hình
    if config.MT5_LOGIN:
        authorized = mt5.login(
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER
        )
        if not authorized:
            print(f"Đăng nhập tài khoản {config.MT5_LOGIN} thất bại. Mã lỗi: {mt5.last_error()}")
            return False
        else:
            print(f"Đăng nhập tài khoản {config.MT5_LOGIN} thành công.")
    else:
        print("Đã kết nối với Terminal MT5 hiện tại đang hoạt động.")
    
    return True

def shutdown_mt5():
    """Ngắt kết nối với MetaTrader 5."""
    mt5.shutdown()
    print("Đã ngắt kết nối MetaTrader 5.")

def get_actual_symbol(symbol_name=config.SYMBOL):
    """Tìm tên ký hiệu chính xác trên sàn giao dịch (Ví dụ XAUUSD, XAUUSD.m, GOLD...)."""
    symbols = mt5.symbols_get()
    if symbols is None:
        return symbol_name
    
    for s in symbols:
        if symbol_name.upper() in s.name.upper():
            # Chọn ký hiệu trùng khớp chính xác nhất
            return s.name
    return symbol_name

def get_rates(symbol, timeframe_str, count=300):
    """
    Lấy dữ liệu nến lịch sử.
    timeframe_str: 'M15' hoặc 'H1'
    count: số nến cần lấy
    """
    # Bản đồ quy đổi khung thời gian
    tf_map = {
        'M15': mt5.TIMEFRAME_M15,
        'H1': mt5.TIMEFRAME_H1
    }
    
    if timeframe_str not in tf_map:
        raise ValueError(f"Khung thời gian không hợp lệ: {timeframe_str}. Chỉ chấp nhận 'M15' hoặc 'H1'.")
        
    tf = tf_map[timeframe_str]
    actual_symbol = get_actual_symbol(symbol)
    
    # Kiểm tra xem ký hiệu có sẵn trong Market Watch không, nếu không thì thêm vào
    selected = mt5.symbol_select(actual_symbol, True)
    if not selected:
        print(f"Không thể chọn ký hiệu {actual_symbol} trong Market Watch.")
        return None
        
    # Copy dữ liệu nến từ vị trí hiện tại (pos=0) ngược về quá khứ
    rates = mt5.copy_rates_from_pos(actual_symbol, tf, 0, count)
    
    if rates is None or len(rates) == 0:
        print(f"Không thể lấy dữ liệu cho {actual_symbol} trên khung {timeframe_str}. Mã lỗi: {mt5.last_error()}")
        return None
        
    # Chuyển đổi thành DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Sắp xếp theo thời gian tăng dần (nến cũ trước, nến mới sau)
    df = df.sort_values('time').reset_index(drop=True)
    return df

# Để test nhanh mô-đun này độc lập
if __name__ == "__main__":
    if initialize_mt5():
        sym = get_actual_symbol()
        print(f"Ký hiệu thực tế trên sàn: {sym}")
        
        print("\nThử lấy 5 nến khung H1 gần nhất:")
        rates_h1 = get_rates(sym, 'H1', 5)
        if rates_h1 is not None:
            print(rates_h1[['time', 'open', 'high', 'low', 'close']])
            
        print("\nThử lấy 5 nến khung M15 gần nhất:")
        rates_m15 = get_rates(sym, 'M15', 5)
        if rates_m15 is not None:
            print(rates_m15[['time', 'open', 'high', 'low', 'close']])
            
        shutdown_mt5()
