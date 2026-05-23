import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import data_provider
import strategy
import config
import indicators

def get_clean_h1_slice(df_h1, df_m15_slice, current_time):
    """
    Tạo DataFrame H1 không có lookahead bias bằng cách loại bỏ phần nến H1 tương lai 
    và dựng lại nến H1 đang hình thành (forming H1 candle) từ các nến M15 đã đóng.
    """
    # Làm tròn thời gian hiện tại về đầu giờ
    floored_hour = current_time.replace(minute=0, second=0, microsecond=0)
    
    # Lấy các nến H1 đã đóng hoàn toàn trước giờ hiện tại
    h1_slice = df_h1[df_h1['time'] < floored_hour].copy()
    
    # Lấy các nến M15 trong giờ hiện tại tính đến thời điểm hiện tại
    current_hour_m15 = df_m15_slice[df_m15_slice['time'] >= floored_hour]
    
    if not current_hour_m15.empty:
        # Dựng lại nến H1 đang hình thành
        forming_h1 = {
            'time': floored_hour,
            'open': current_hour_m15['open'].iloc[0],
            'high': current_hour_m15['high'].max(),
            'low': current_hour_m15['low'].min(),
            'close': current_hour_m15['close'].iloc[-1]
        }
        
        # Sao chép các cột khác (atr, volume, v.v...) nếu có trong df_h1
        for col in df_h1.columns:
            if col not in forming_h1:
                if col == 'tick_volume' and 'tick_volume' in current_hour_m15.columns:
                    forming_h1[col] = current_hour_m15['tick_volume'].sum()
                elif col == 'real_volume' and 'real_volume' in current_hour_m15.columns:
                    forming_h1[col] = current_hour_m15['real_volume'].sum()
                elif col == 'spread' and 'spread' in current_hour_m15.columns:
                    forming_h1[col] = current_hour_m15['spread'].iloc[-1]
                else:
                    forming_h1[col] = 0.0
                    
        # Thêm nến H1 đang hình thành vào slice
        forming_df = pd.DataFrame([forming_h1])
        h1_slice = pd.concat([h1_slice, forming_df], ignore_index=True)
        
    return h1_slice

def run_simulation(df_m15, df_h1, symbol_name, tp_mode="H1_SWING"):
    """
    Chạy mô phỏng giao dịch lịch sử với một chế độ chốt lời (TP) cụ thể.
    Các chế độ tp_mode:
    - 'H1_SWING': Dùng đỉnh/đáy H1 gần nhất làm TP (Mặc định).
    - 'RR_1.5': Đặt TP cố định ở tỷ lệ 1:1.5 RR.
    - 'RR_2.0': Đặt TP cố định ở tỷ lệ 1:2.0 RR.
    - 'PARTIAL_1.5': Chốt 50% ở 1.5 RR, 50% còn lại gồng về TP của H1 Swing (Có dời SL về BE tại 1:1 RR và Trailing Stop cấu trúc).
    """
    trades = []
    active_trade = None
    total_steps = len(df_m15)
    
    i = 300
    while i < total_steps:
        current_m15_row = df_m15.iloc[i]
        current_time = current_m15_row['time']
        current_close = current_m15_row['close']
        current_high = current_m15_row['high']
        current_low = current_m15_row['low']
        
        # 1. Nếu đang có lệnh mở, kiểm tra đóng lệnh hoặc dời SL
        if active_trade is not None:
            risk_dist = active_trade['risk_distance']
            entry = active_trade['entry']
            
            # Kiểm tra dời SL về hòa vốn (0.8 RR)
            if not active_trade['be_moved']:
                if active_trade['type'] == 'BUY':
                    if current_high >= entry + (risk_dist * 0.8):
                        active_trade['sl'] = entry
                        active_trade['be_moved'] = True
                else: # SELL
                    if current_low <= entry - (risk_dist * 0.8):
                        active_trade['sl'] = entry
                        active_trade['be_moved'] = True
                        
            # Kiểm tra chốt lời từng phần (Partial TP)
            if tp_mode == 'PARTIAL_1.5' and not active_trade['partial_taken']:
                partial_tp_dist = risk_dist * 1.5
                if active_trade['type'] == 'BUY':
                    if current_high >= entry + partial_tp_dist:
                        active_trade['partial_taken'] = True
                        active_trade['partial_time'] = current_time
                else: # SELL
                    if current_low <= entry - partial_tp_dist:
                        active_trade['partial_taken'] = True
                        active_trade['partial_time'] = current_time
            
            # Trailing Stop cấu trúc cho PARTIAL_1.5 sau khi chốt lời 50%
            if tp_mode == 'PARTIAL_1.5' and active_trade['partial_taken']:
                # Lấy 100 nến M15 tính đến thời điểm hiện tại i để quét cấu trúc swing
                df_m15_slice = df_m15.iloc[i-99 : i+1].copy().reset_index(drop=True)
                sh_m15, sl_m15 = indicators.find_swings(df_m15_slice, left=4, right=2)
                
                if active_trade['type'] == 'BUY':
                    latest_sl = sl_m15[-1]['price'] if sl_m15 else 0.0
                    # SL mới phải cao hơn SL hiện tại và thấp hơn giá hiện tại
                    if latest_sl > 0.0 and latest_sl > active_trade['sl'] and latest_sl < current_close:
                        active_trade['sl'] = latest_sl
                else: # SELL
                    latest_sl = sh_m15[-1]['price'] if sh_m15 else 0.0
                    # SL mới phải thấp hơn SL hiện tại và cao hơn giá hiện tại
                    if latest_sl > 0.0 and latest_sl < active_trade['sl'] and latest_sl > current_close:
                        active_trade['sl'] = latest_sl
            
            # Kiểm tra đóng lệnh (SL hoặc TP chính)
            closed = False
            exit_price = 0.0
            status = ""
            
            if active_trade['type'] == 'BUY':
                if current_low <= active_trade['sl']:
                    closed = True
                    exit_price = active_trade['sl']
                    status = "SL" if not active_trade['be_moved'] else "BE"
                elif current_high >= active_trade['tp']:
                    closed = True
                    exit_price = active_trade['tp']
                    status = "TP"
            else: # SELL
                if current_high >= active_trade['sl']:
                    closed = True
                    exit_price = active_trade['sl']
                    status = "SL" if not active_trade['be_moved'] else "BE"
                elif current_low <= active_trade['tp']:
                    closed = True
                    exit_price = active_trade['tp']
                    status = "TP"
                    
            if closed:
                # Tính toán PnL giả lập tiền tệ dựa trên tài khoản 10k, rủi ro 1% (100 USD)
                pnl_usd = 0.0
                if tp_mode == 'PARTIAL_1.5':
                    if status == 'TP':
                        # Thắng toàn bộ: 50% ăn 1.5 RR (+75 USD), 50% ăn H1 Swing RR
                        rr_h1 = abs(active_trade['tp'] - entry) / risk_dist
                        pnl_usd = 50.0 * 1.5 + 50.0 * rr_h1
                    else: # SL hoặc BE
                        if active_trade['partial_taken']:
                            # Đã ăn 50% tại 1.5 RR (+75 USD), 50% còn lại đóng ở exit_price
                            remaining_risk_ratio = (exit_price - entry) / risk_dist if active_trade['type'] == 'BUY' else (entry - exit_price) / risk_dist
                            pnl_usd = 50.0 * 1.5 + 50.0 * remaining_risk_ratio
                        elif active_trade['be_moved']:
                            pnl_usd = 0.0
                        else:
                            pnl_usd = -100.0
                else:
                    # Chế độ bình thường
                    if status == 'SL':
                        pnl_usd = -100.0
                    elif status == 'BE':
                        pnl_usd = 0.0
                    elif status == 'TP':
                        rr = abs(active_trade['tp'] - entry) / risk_dist
                        pnl_usd = 100.0 * rr
                
                active_trade['exit_time'] = current_time
                active_trade['exit_price'] = exit_price
                active_trade['status'] = status
                active_trade['pnl_usd'] = pnl_usd
                active_trade['pnl_points'] = (exit_price - entry) if active_trade['type'] == 'BUY' else (entry - exit_price)
                
                trades.append(active_trade)
                active_trade = None
                
        # 2. Nếu chưa có lệnh, tìm tín hiệu mới
        else:
            df_m15_slice = df_m15.iloc[i-299 : i+1].copy().reset_index(drop=True)
            h1_slice = get_clean_h1_slice(df_h1, df_m15_slice, current_time)
            
            if len(h1_slice) >= 300:
                df_h1_slice = h1_slice.iloc[-300:].reset_index(drop=True)
                
                # Chạy phân tích chiến lược (tắt print log để tránh rối mắt)
                import builtins
                original_print = builtins.print
                builtins.print = lambda *args, **kwargs: None
                try:
                    signal, _ = strategy.analyze_market(symbol_name, df_h1_slice, df_m15_slice)
                finally:
                    builtins.print = original_print
                    
                if signal is not None:
                    entry_price = signal['entry']
                    sl = signal['sl']
                    tp = signal['tp']
                    risk_dist = abs(entry_price - sl)
                    
                    if risk_dist > 0:
                        # Thay đổi TP dựa trên tp_mode
                        if tp_mode == 'RR_1.5':
                            tp = entry_price + (risk_dist * 1.5) if signal['action'] == 'BUY' else entry_price - (risk_dist * 1.5)
                        elif tp_mode == 'RR_2.0':
                            tp = entry_price + (risk_dist * 2.0) if signal['action'] == 'BUY' else entry_price - (risk_dist * 2.0)
                            
                        active_trade = {
                            'symbol': symbol_name.upper(),
                            'type': signal['action'],
                            'entry_time': current_time,
                            'entry': entry_price,
                            'sl': sl,
                            'tp': tp,
                            'risk_distance': risk_dist,
                            'be_moved': False,
                            'partial_taken': False,
                            'partial_time': None,
                            'exit_time': None,
                            'exit_price': 0.0,
                            'status': "OPEN",
                            'pnl_usd': 0.0,
                            'pnl_points': 0.0
                        }
        i += 1
    return trades

def print_monthly_report(trades, symbol_info=""):
    """
    Thống kê chi tiết và in ra bảng hiệu suất của chiến thuật PARTIAL_1.5 theo từng tháng.
    Tối ưu hóa giao diện hiển thị bằng cách dọc hóa (Tháng là hàng, Chỉ số là cột) để tránh vỡ dòng.
    """
    # Sort trades by exit time
    trades = sorted([t for t in trades if t['exit_time'] is not None], key=lambda x: x['exit_time'])
    if not trades:
        print("[-] Không có giao dịch nào hoàn tất trong quá trình mô phỏng.")
        return
        
    start_balance = 10000.0
    balance = start_balance
    peak = start_balance
    
    # Lấy rủi ro mặc định từ file cấu hình .env (config.RISK_PERCENT)
    risk_percent = float(config.RISK_PERCENT)
    pnl_multiplier = risk_percent
    
    equity_curve = []
    for t in trades:
        pnl = t['pnl_usd'] * pnl_multiplier
        balance += pnl
        if balance > peak:
            peak = balance
        dd_usd = peak - balance
        dd_pct = (dd_usd / peak) * 100
        
        equity_curve.append({
            'trade': t,
            'balance': balance,
            'pnl': pnl,
            'peak': peak,
            'dd_pct': dd_pct,
            'exit_time': t['exit_time']
        })
        
    df_equity = pd.DataFrame(equity_curve)
    df_equity['month'] = df_equity['exit_time'].apply(lambda x: x.strftime('%Y-%m'))
    months = sorted(df_equity['month'].unique())
    
    monthly_data = []
    prev_month_balance = start_balance
    
    # Track overall statistics
    overall_total = len(trades)
    overall_tps = [t for t in trades if t['status'] == 'TP']
    overall_sls = [t for t in trades if t['status'] == 'SL']
    overall_bes = [t for t in trades if t['status'] == 'BE']
    overall_partial_wins = [t for t in trades if t['status'] == 'BE' and t['partial_taken']]
    
    overall_win_rate = ((len(overall_tps) + len(overall_partial_wins)) / overall_total * 100) if overall_total > 0 else 0.0
    overall_return = ((balance - start_balance) / start_balance) * 100
    overall_max_dd = df_equity['dd_pct'].max() if not df_equity.empty else 0.0
    
    for m in months:
        m_trades = df_equity[df_equity['month'] == m]
        
        total_trades = len(m_trades)
        tps = m_trades[m_trades['trade'].apply(lambda x: x['status'] == 'TP')]
        sls = m_trades[m_trades['trade'].apply(lambda x: x['status'] == 'SL')]
        bes = m_trades[m_trades['trade'].apply(lambda x: x['status'] == 'BE')]
        partial_wins = m_trades[m_trades['trade'].apply(lambda x: x['status'] == 'BE' and x['partial_taken'])]
        
        num_tp = len(tps) + len(partial_wins)
        num_sl = len(sls)
        num_be = len(bes) - len(partial_wins)
        
        win_rate = (num_tp / total_trades * 100) if total_trades > 0 else 0.0
        
        # Monthly return
        m_start_balance = prev_month_balance
        m_end_balance = m_trades.iloc[-1]['balance']
        profit_pct = ((m_end_balance - m_start_balance) / m_start_balance) * 100
        cum_profit_pct = ((m_end_balance - start_balance) / start_balance) * 100
        
        # Monthly Max Drawdown
        m_peak = m_start_balance
        m_max_dd_pct = 0.0
        curr_bal = m_start_balance
        for idx, row in m_trades.iterrows():
            curr_bal += row['pnl']
            if curr_bal > m_peak:
                m_peak = curr_bal
            m_dd = (m_peak - curr_bal) / m_peak * 100
            if m_dd > m_max_dd_pct:
                m_max_dd_pct = m_dd
                
        monthly_data.append({
            'month': m,
            'total': total_trades,
            'win_rate': win_rate,
            'tp_sl_be': f"{num_tp}/{num_sl}/{num_be}",
            'return_pct': profit_pct,
            'cum_return_pct': cum_profit_pct,
            'max_dd_pct': m_max_dd_pct
        })
        prev_month_balance = m_end_balance
        
    print("\n" + "="*95)
    print(f" BẢNG HIỆU SUẤT CHI TIẾT CHIẾN THUẬT PARTIAL_1.5 THEO THÁNG | {symbol_info.upper()}")
    print(f" Cấu hình rủi ro: {risk_percent}%/lệnh | Vốn ban đầu: ${start_balance:,.2f}")
    print("="*95)
    
    # In tiêu đề cột
    header = f" {'Tháng':<10} | {'Số lệnh':<8} | {'Winrate':<8} | {'TP/SL/BE':<10} | {'LN Tháng':<12} | {'LN Lũy Kế':<12} | {'DD Max':<10}"
    print(header)
    print("-"*len(header))
    
    # In từng dòng tháng
    for row in monthly_data:
        print(f" {row['month']:<10} | {row['total']:<8} | {row['win_rate']:7.1f}% | {row['tp_sl_be']:<10} | {row['return_pct']:+11.2f}% | {row['cum_return_pct']:+11.2f}% | {row['max_dd_pct']:9.2f}%")
        
    print("-"*len(header))
    # In dòng cả kỳ
    overall_tp_sl_be_str = f"{len(overall_tps) + len(overall_partial_wins)}/{len(overall_sls)}/{len(overall_bes) - len(overall_partial_wins)}"
    print(f" {'Cả kỳ':<10} | {overall_total:<8} | {overall_win_rate:7.1f}% | {overall_tp_sl_be_str:<10} | {overall_return:+11.2f}% | {overall_return:+11.2f}% | {overall_max_dd:9.2f}%")
    print("="*95)
    
    # Xuất lịch sử lệnh ra CSV
    try:
        df_trades = pd.DataFrame(trades)
        columns_to_save = ['symbol', 'type', 'entry_time', 'entry', 'sl', 'tp', 'risk_distance', 'be_moved', 'partial_taken', 'exit_time', 'exit_price', 'status', 'pnl_usd', 'pnl_points']
        df_trades = df_trades[columns_to_save]
        csv_file = config.BASE_DIR / f"backtest_report_{symbol_info.lower().replace(' ', '_')}.csv"
        df_trades.to_csv(csv_file, index=False, encoding='utf-8')
        print(f"📝 Đã xuất lịch sử lệnh ra file CSV: {csv_file.name}")
    except Exception as e:
        print(f"Không thể xuất file CSV: {e}")

def run_backtest_experiment(symbol_name="XAUUSD", days=45):
    """Chạy thử nghiệm kiểm thử chi tiết và in báo cáo theo tháng cho 1 symbol."""
    print("="*70)
    print(f" KHỞI CHẠY BACKTEST CHO CẶP: {symbol_name.upper()} ")
    print(f" Thời gian kiểm thử: {days} ngày gần nhất")
    print("="*70)
    
    if not data_provider.initialize_mt5():
        print("Lỗi: Không thể kết nối tới MT5.")
        return
        
    actual_sym = data_provider.get_actual_symbol(symbol_name)
    if not mt5.symbol_select(actual_sym, True):
        print(f"Lỗi: Không thể chọn ký hiệu {actual_sym}")
        data_provider.shutdown_mt5()
        return
        
    m15_count = int(days * 96) + 300
    h1_count = int(days * 24) + 300
    
    print(f"Đang tải dữ liệu từ MT5 cho {actual_sym}...")
    df_h1 = data_provider.get_rates(actual_sym, 'H1', h1_count)
    df_m15 = data_provider.get_rates(actual_sym, 'M15', m15_count)
    
    if df_h1 is None or df_m15 is None or len(df_h1) < 250 or len(df_m15) < 250:
        print("Lỗi: Không đủ dữ liệu lịch sử để chạy Backtest.")
        data_provider.shutdown_mt5()
        return
        
    print(f"Đã tải thành công {len(df_h1)} nến H1 và {len(df_m15)} nến M15.")
    data_provider.shutdown_mt5()
    
    print("\nĐang mô phỏng chiến thuật chốt lời PARTIAL_1.5...")
    trades = run_simulation(df_m15, df_h1, symbol_name, tp_mode='PARTIAL_1.5')
    print_monthly_report(trades, symbol_info=symbol_name)

def run_multi_symbol_backtest(days=45):
    """Chạy kiểm thử lịch sử trên toàn bộ các tài sản cho phép cùng lúc."""
    print("="*95)
    print(f" KHỞI CHẠY BACKTEST ĐA TÀI SẢN (MULTI-SYMBOL BACKTEST) | THỜI GIAN: {days} NGÀY ")
    print("="*95)
    print(f"Danh sách tài sản cho phép quét: {config.SYMBOLS}")
    
    if not data_provider.initialize_mt5():
        print("Lỗi: Không thể kết nối tới MT5.")
        return
        
    all_trades = []
    for sym in config.SYMBOLS:
        print(f"\n[+] Đang tải dữ liệu lịch sử và chạy mô phỏng cho {sym}...")
        actual_sym = data_provider.get_actual_symbol(sym)
        if not mt5.symbol_select(actual_sym, True):
            print(f"Cảnh báo: Không thể chọn ký hiệu {actual_sym} trên sàn. Bỏ qua.")
            continue
            
        m15_count = int(days * 96) + 300
        h1_count = int(days * 24) + 300
        df_h1 = data_provider.get_rates(actual_sym, 'H1', h1_count)
        df_m15 = data_provider.get_rates(actual_sym, 'M15', m15_count)
        
        if df_h1 is None or df_m15 is None or len(df_h1) < 250 or len(df_m15) < 250:
            print(f"Cảnh báo: Không đủ dữ liệu cho {sym}. Yêu cầu tối thiểu 250 nến.")
            continue
            
        trades = run_simulation(df_m15, df_h1, sym, tp_mode='PARTIAL_1.5')
        all_trades.extend(trades)
        print(f"-> Hoàn tất {sym}: {len(trades)} lệnh")
        
    data_provider.shutdown_mt5()
    
    print_monthly_report(all_trades, symbol_info="XAUUSD_GBPUSD")


if __name__ == "__main__":
    import sys
    symbol = "ALL"
    days = 45
    
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            days = int(sys.argv[2])
        except ValueError:
            pass
            
    if symbol.upper() == "ALL":
        run_multi_symbol_backtest(days)
    else:
        run_backtest_experiment(symbol, days)
