import sys
sys.path.append(r'C:\Users\Duc\.gemini\antigravity\scratch\xauusd_trading_bot')
import data_provider
import indicators
import chart_plotter
import MetaTrader5 as mt5

def main():
    print("=== DANG LAY DU LIEU VA VE BIEU DO ANH MAU ===")
    if not data_provider.initialize_mt5():
        print("Lỗi: Không thể kết nối Terminal MT5")
        return
        
    symbol = "XAUUSD"
    actual_sym = data_provider.get_actual_symbol(symbol)
    
    print(f"Fetching M15 bars for {actual_sym}...")
    df_m15 = data_provider.get_rates(actual_sym, 'M15', 120)
    
    if df_m15 is not None:
        # 1. Tính toán các swing đỉnh/đáy, FVG, OB để vẽ hợp lưu
        sh_m15, sl_m15 = indicators.find_swings(df_m15, left=4, right=2)
        fvgs = indicators.find_fvgs(df_m15, lookback=40)
        obs = indicators.find_order_blocks(df_m15, sh_m15, sl_m15, lookback=80)
        
        # 2. Tạo một lệnh giả lập để minh họa
        entry_price = df_m15['close'].iloc[-1]
        # Giả định lệnh BUY
        sl = entry_price - 8.5 # Khoảng cách SL khoảng 8.5$
        tp = entry_price + 12.75 # 1.5 RR TP
        
        dest_path = r"C:\Users\Duc\.gemini\antigravity\brain\641e3479-d98a-4ba2-a577-bc54bb3a849b\chart_sample.png"
        print(f"Plotting chart with Entry: {entry_price}, SL: {sl}, TP: {tp}")
        success = chart_plotter.plot_trade_chart(symbol, df_m15, entry_price, sl, tp, fvgs, obs, dest_path)
        if success:
            print("Đã vẽ biểu đồ và lưu ảnh thành công!")
        else:
            print("Vẽ biểu đồ thất bại.")
    else:
        print("Không thể lấy dữ liệu nến M15 từ MT5.")
        
    mt5.shutdown()

if __name__ == '__main__':
    main()
