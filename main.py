import time
import json
from datetime import datetime, timedelta
from pathlib import Path
import MetaTrader5 as mt5
import data_provider
import strategy
import notifier
import indicators
import config
# Đường dẫn lưu trạng thái các lệnh giao dịch để quản lý chốt lời từng phần
STATE_FILE = config.BASE_DIR / "position_state.json"
def load_position_states():
    """Tải trạng thái các lệnh từ file JSON."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Lỗi đọc file trạng thái vị thế: {e}")
    return {}
def save_position_states(states):
    """Lưu trạng thái các lệnh vào file JSON."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(states, f, indent=4)
    except Exception as e:
        print(f"Lỗi ghi file trạng thái vị thế: {e}")
def get_safety_metrics():
    """
    Quét lịch sử giao dịch trong ngày hôm nay và chuỗi thua lỗ gần nhất từ MT5.
    Trả về: (daily_dd_pct, consecutive_losses)
    """
    now = datetime.now()
    start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0)
    
    # Lấy lịch sử giao dịch từ đầu ngày đến hiện tại
    deals = mt5.history_deals_get(start_of_day, now)
    daily_pnl_usd = 0.0
    if deals is not None:
        for d in deals:
            if d.magic == config.MAGIC_NUMBER and d.entry in [1, 2]:
                daily_pnl_usd += d.profit + d.commission + d.swap
    # Lấy thêm lịch sử 7 ngày gần nhất để tính chuỗi thua liên tiếp
    start_of_week = now - timedelta(days=7)
    week_deals = mt5.history_deals_get(start_of_week, now)
    consecutive_losses = 0
    if week_deals is not None:
        bot_deals = [d for d in week_deals if d.magic == config.MAGIC_NUMBER and d.entry in [1, 2]]
        bot_deals = sorted(bot_deals, key=lambda x: x.time)
        
        for d in reversed(bot_deals):
            pnl = d.profit + d.commission + d.swap
            if pnl < -1.0: # Thua lỗ đáng kể
                consecutive_losses += 1
            elif pnl > 1.0: # Thắng đáng kể -> Cắt chuỗi thua
                break
    # Tính phần trăm sụt giảm so với Balance hiện tại + lỗ hôm nay (Vốn đầu ngày)
    acct = mt5.account_info()
    daily_dd_pct = 0.0
    if acct is not None and daily_pnl_usd < 0:
        start_balance = acct.balance - daily_pnl_usd
        if start_balance > 0:
            daily_dd_pct = (abs(daily_pnl_usd) / start_balance) * 100
            
    return daily_dd_pct, consecutive_losses
def get_seconds_until_next_m15():
    """Tính số giây cho tới khi nến M15 tiếp theo bắt đầu (cộng 5 giây buffer)."""
    now = datetime.now()
    minutes_to_next = 15 - (now.minute % 15)
    seconds_to_next = (minutes_to_next * 60) - now.second
    return max(5, seconds_to_next + 5)
def calculate_lot_size(symbol, sl_distance):
    """Tính toán số Lot dựa trên rủi ro tài khoản và khoảng cách Stop Loss."""
    acct = mt5.account_info()
    if acct is None:
        print("Không thể lấy thông tin tài khoản MT5 để tính Lot size.")
        return 0.01
        
    balance = acct.balance
    risk_usd = balance * config.RISK_PERCENT / 100.0
    
    info = mt5.symbol_info(symbol)
    if info is None:
        print(f"Không thể lấy thông tin symbol {symbol} để tính Lot size.")
        return 0.01
        
    tick_size = info.trade_tick_size
    tick_value = info.trade_tick_value
    
    if tick_size == 0 or tick_value == 0 or sl_distance == 0:
        return info.volume_min
        
    # Tính số points của khoảng cách SL
    points_distance = sl_distance / tick_size
    
    # Tính Lot size
    lot_size = risk_usd / (points_distance * tick_value)
    
    # Ràng buộc số Lot theo giới hạn của sàn
    lot_size = max(info.volume_min, min(info.volume_max, lot_size))
    
    # Tròn theo volume_step
    step = info.volume_step
    lot_size = round(lot_size / step) * step
    
    # Bo tròn phần thập phân theo độ chính xác của volume_step
    decimals = 0
    s = str(step)
    if "." in s:
        decimals = len(s.split(".")[1])
    lot_size = round(lot_size, decimals)
    
    return lot_size
def execute_auto_trade(symbol, action, sl, tp):
    """Đặt lệnh tự động trên MT5."""
    if not mt5.symbol_select(symbol, True):
        return False, 0.0, f"Không thể chọn {symbol} trong Market Watch."
        
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return False, 0.0, f"Không thể lấy thông tin {symbol}."
        
    # Lấy giá hiện tại
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return False, 0.0, f"Không thể lấy tick giá cho {symbol}."
        
    order_type = mt5.ORDER_TYPE_BUY if action == 'BUY' else mt5.ORDER_TYPE_SELL
    price = tick.ask if action == 'BUY' else tick.bid
    sl_distance = abs(price - sl)
    
    # Kiểm tra Spread so với khoảng cách Stop Loss để tránh slippage và tin tức quét hai đầu
    spread = tick.ask - tick.bid
    max_allowed_spread = sl_distance * 0.30
    if spread > max_allowed_spread:
        err_msg = f"Spread qua rong ({spread:.5f} > 30% SL {max_allowed_spread:.5f})"
        print(f"[{symbol.upper()}] Bo qua dat lenh: {err_msg}")
        return False, 0.0, err_msg
        
    lot = calculate_lot_size(symbol, sl_distance)
    
    # Xác định filling mode
    filling = mt5.ORDER_FILLING_FOK
    if symbol_info.filling_mode & mt5.SYMBOL_FILLING_FOK:
        filling = mt5.ORDER_FILLING_FOK
    elif symbol_info.filling_mode & mt5.SYMBOL_FILLING_IOC:
        filling = mt5.ORDER_FILLING_IOC
    else:
        filling = mt5.ORDER_FILLING_RETURN
        
    # Chuẩn bị yêu cầu giao dịch
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": config.MAGIC_NUMBER,
        "comment": "Antigravity Bot Auto",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling,
    }
    
    print(f"[{symbol.upper()}] Gửi yêu cầu đặt lệnh: {action} {lot} Lot tại {price:.5f} (SL: {sl:.5f}, TP: {tp:.5f})")
    result = mt5.order_send(request)
    
    if result is None:
        return False, 0.0, "Hàm order_send trả về None."
        
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        err_msg = f"Đặt lệnh thất bại. Code: {result.retcode}, Comment: {result.comment}"
        print(f"[{symbol.upper()}] {err_msg}")
        return False, 0.0, result.comment
        
    print(f"[{symbol.upper()}] Đặt lệnh thành công. Ticket: #{result.order}, Volume: {result.volume} Lot")
    return True, result.volume, result.order
def close_partial_position(pos, half_lot):
    """Đóng một nửa khối lượng vị thế (chốt lời từng phần)."""
    tick = mt5.symbol_info_tick(pos.symbol)
    symbol_info = mt5.symbol_info(pos.symbol)
    if tick is None or symbol_info is None:
        return False, "Không thể lấy thông tin giá hoặc symbol."
        
    order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
    
    # Xác định filling mode
    filling = mt5.ORDER_FILLING_FOK
    if symbol_info.filling_mode & mt5.SYMBOL_FILLING_FOK:
        filling = mt5.ORDER_FILLING_FOK
    elif symbol_info.filling_mode & mt5.SYMBOL_FILLING_IOC:
        filling = mt5.ORDER_FILLING_IOC
    else:
        filling = mt5.ORDER_FILLING_RETURN
        
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": pos.symbol,
        "volume": half_lot,
        "type": order_type,
        "position": pos.ticket,
        "price": price,
        "deviation": 20,
        "magic": config.MAGIC_NUMBER,
        "comment": "Bot Partial TP 50%",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling,
    }
    
    res = mt5.order_send(request)
    if res is None:
        return False, "Hàm order_send trả về None."
    if res.retcode != mt5.TRADE_RETCODE_DONE:
        return False, res.comment
        
    return True, res.price
def manage_active_trades():
    """Kiểm tra các lệnh đang chạy để dời SL về hòa vốn (1:1 RR) và chốt lời 50% (1.5 RR)."""
    positions = mt5.positions_get(magic=config.MAGIC_NUMBER)
    states = load_position_states()
    
    # 1. Dọn dẹp trạng thái: Xóa những ticket không còn mở nữa để file JSON luôn nhẹ
    active_tickets = {str(pos.ticket) for pos in positions} if positions else set()
    states_to_clean = [t for t in states if t not in active_tickets]
    for t in states_to_clean:
        del states[t]
    if states_to_clean:
        save_position_states(states)
        
    if positions is None or len(positions) == 0:
        return
        
    for pos in positions:
        ticket_str = str(pos.ticket)
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            continue
            
        entry_price = pos.price_open
        
        # Đồng bộ trạng thái lưu trong file
        if ticket_str in states:
            trade_state = states[ticket_str]
            original_sl = trade_state.get("original_sl", pos.sl)
            risk_distance = trade_state.get("risk_distance", abs(entry_price - original_sl))
        else:
            # Nếu chưa có trong file (ví dụ lệnh được đặt trước khi nâng cấp hoặc lỗi đồng bộ)
            original_sl = pos.sl
            risk_distance = abs(entry_price - original_sl)
            trade_state = {
                "original_sl": original_sl,
                "original_tp": pos.tp,
                "entry_price": entry_price,
                "risk_distance": risk_distance,
                "partial_taken": False,
                "be_moved": abs(pos.sl - entry_price) < 0.00001
            }
            states[ticket_str] = trade_state
            save_position_states(states)
            
        if risk_distance <= 0:
            continue
            
        # A. Kiểm tra dời SL về hòa vốn (0.8 RR)
        if not trade_state.get("be_moved", False):
            should_move_sl = False
            if pos.type == mt5.POSITION_TYPE_BUY:
                current_price = tick.bid
                if current_price >= entry_price + (risk_distance * 0.8):
                    should_move_sl = True
            else: # POSITION_TYPE_SELL
                current_price = tick.ask
                if current_price <= entry_price - (risk_distance * 0.8):
                    should_move_sl = True
                    
            if should_move_sl:
                print(f"[{pos.symbol.upper()}] Lệnh #{pos.ticket} đạt 0.8 RR. Đang dời SL về hòa vốn ({entry_price:.5f})...")
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": pos.ticket,
                    "sl": entry_price,
                    "tp": pos.tp
                }
                res = mt5.order_send(request)
                if res is not None and res.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"[{pos.symbol.upper()}] Đã dời SL về Entry cho lệnh #{pos.ticket} thành công.")
                    trade_state["be_moved"] = True
                    states[ticket_str] = trade_state
                    save_position_states(states)
                    notifier.send_break_even_notification(pos.symbol, pos.ticket, entry_price)
                else:
                    err_code = res.retcode if res else "None"
                    print(f"[{pos.symbol.upper()}] Dời SL về Entry thất bại cho lệnh #{pos.ticket}. Code: {err_code}")
                    
        # B. Kiểm tra chốt lời từng phần 50% khối lượng (1.5 RR)
        if not trade_state.get("partial_taken", False):
            should_take_partial = False
            if pos.type == mt5.POSITION_TYPE_BUY:
                current_price = tick.bid
                if current_price >= entry_price + (risk_distance * 1.5):
                    should_take_partial = True
            else: # POSITION_TYPE_SELL
                current_price = tick.ask
                if current_price <= entry_price - (risk_distance * 1.5):
                    should_take_partial = True
                    
            if should_take_partial:
                symbol_info = mt5.symbol_info(pos.symbol)
                if symbol_info is not None:
                    step = symbol_info.volume_step
                    min_vol = symbol_info.volume_min
                    
                    # Tính 50% khối lượng hiện tại của vị thế
                    half_lot = round((pos.volume / 2.0) / step) * step
                    half_lot = max(min_vol, half_lot)
                    
                    # Làm tròn số thập phân của Lot theo sàn quy định
                    decimals = 0
                    s_step = str(step)
                    if "." in s_step:
                        decimals = len(s_step.split(".")[1])
                    half_lot = round(half_lot, decimals)
                    
                    print(f"[{pos.symbol.upper()}] Lệnh #{pos.ticket} đạt 1.5 RR. Tiến hành chốt lời 50% ({half_lot} Lot)...")
                    success, exec_price_or_err = close_partial_position(pos, half_lot)
                    
                    if success:
                        print(f"[{pos.symbol.upper()}] Chốt lời 50% thành công lệnh #{pos.ticket} tại {exec_price_or_err:.5f}.")
                        trade_state["partial_taken"] = True
                        states[ticket_str] = trade_state
                        save_position_states(states)
                        notifier.send_partial_tp_notification(pos.symbol, pos.ticket, half_lot, exec_price_or_err)
                    else:
                        print(f"[{pos.symbol.upper()}] Chốt lời 50% thất bại lệnh #{pos.ticket}: {exec_price_or_err}")
                        
        # C. Trailing Stop cấu trúc sau khi đã chốt lời 50%
        else: # partial_taken is True
            # Tải dữ liệu M15 gần nhất để tìm swing mới
            df_m15 = data_provider.get_rates(pos.symbol, 'M15', 100)
            if df_m15 is not None:
                # Tính các swing high/low gần nhất
                sh_m15, sl_m15 = indicators.find_swings(df_m15, left=4, right=2)
                
                if pos.type == mt5.POSITION_TYPE_BUY:
                    # Đáy swing low M15 gần nhất làm SL mới
                    latest_sl = sl_m15[-1]['price'] if sl_m15 else 0.0
                    # SL mới phải cao hơn SL hiện tại và thấp hơn giá Bid hiện tại để tránh lỗi
                    if latest_sl > 0.0 and latest_sl > pos.sl and latest_sl < tick.bid:
                        print(f"[{pos.symbol.upper()}] Trailing Stop: Đang dời SL của lệnh #{pos.ticket} lên swing low M15 mới {latest_sl:.5f}...")
                        request = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "position": pos.ticket,
                            "sl": latest_sl,
                            "tp": pos.tp
                        }
                        res = mt5.order_send(request)
                        if res is not None and res.retcode == mt5.TRADE_RETCODE_DONE:
                            print(f"[{pos.symbol.upper()}] Trailing Stop thành công lệnh #{pos.ticket} lên {latest_sl:.5f}.")
                            notifier.send_trailing_stop_notification(pos.symbol, pos.ticket, latest_sl)
                else: # POSITION_TYPE_SELL
                    # Đỉnh swing high M15 gần nhất làm SL mới
                    latest_sl = sh_m15[-1]['price'] if sh_m15 else 0.0
                    # SL mới phải thấp hơn SL hiện tại và cao hơn giá Ask hiện tại
                    if latest_sl > 0.0 and latest_sl < pos.sl and latest_sl > tick.ask:
                        print(f"[{pos.symbol.upper()}] Trailing Stop: Đang dời SL của lệnh #{pos.ticket} xuống swing high M15 mới {latest_sl:.5f}...")
                        request = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "position": pos.ticket,
                            "sl": latest_sl,
                            "tp": pos.tp
                        }
                        res = mt5.order_send(request)
                        if res is not None and res.retcode == mt5.TRADE_RETCODE_DONE:
                            print(f"[{pos.symbol.upper()}] Trailing Stop thành công lệnh #{pos.ticket} xuống {latest_sl:.5f}.")
                            notifier.send_trailing_stop_notification(pos.symbol, pos.ticket, latest_sl)
def main():
    print("="*55)
    print(" KHỞI CHẠY CHƯƠNG TRÌNH GIAO DỊCH TỰ ĐỘNG & ĐA TÀI SẢN ")
    print("="*55)
    
    # Khởi tạo kết nối MT5
    if not data_provider.initialize_mt5():
        print("Lỗi: Không thể kết nối tới Terminal MetaTrader 5.")
        return
        
    # Tạo danh sách các cặp giao dịch chính xác trên Market Watch
    actual_symbols = {}
    for sym in config.SYMBOLS:
        actual_sym = data_provider.get_actual_symbol(sym)
        # Kích hoạt ký hiệu trong Market Watch
        if mt5.symbol_select(actual_sym, True):
            actual_symbols[sym] = actual_sym
            print(f"Ký hiệu đã đồng bộ: {sym} -> {actual_sym}")
        else:
            print(f"Cảnh báo: Không thể chọn ký hiệu {sym} trên sàn.")
            
    if not actual_symbols:
        print("Lỗi: Không có cặp giao dịch hợp lệ nào để quét.")
        data_provider.shutdown_mt5()
        return
        
    # Gửi tin nhắn khởi động tới Telegram
    start_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    test_msg = (
        f"🟢 <b>Bot Giao Dịch Đa Tài Sản</b> đã khởi chạy thành công!\n"
        f"🕒 <b>Thời gian:</b> {start_time_str}\n"
        f"⚙️ <b>Auto-Trading:</b> {'BẬT (ON)' if config.AUTO_TRADE else 'TẮT (OFF)'}\n"
        f"🔍 <b>Mã quét:</b> {', '.join(actual_symbols.values())}\n"
        f"⏰ <b>Khung giờ quét (Việt Nam - UTC+7):</b> {config.SESSION_START_HOUR}h - {config.SESSION_END_HOUR}h"
    )
    notifier.send_telegram_message(test_msg)
    
    # Theo dõi nến M15 đã quét của từng cặp
    last_sent_candle_times = {sym: None for sym in actual_symbols}
    # Trạng thái gửi cảnh báo Telegram tránh spam
    last_notified_date = None
    notified_safety = False
    
    try:
        while True:
            try:
                # 1. Quản lý các lệnh đang chạy (Dời SL và Chốt lời từng phần 50%)
                manage_active_trades()
                
                # Kiểm tra các điều kiện an toàn trước khi tìm kiếm tín hiệu mới
                daily_dd, losses = get_safety_metrics()
                current_date = datetime.now().strftime('%Y-%m-%d')
                
                # Reset trạng thái cảnh báo nếu sang ngày mới
                if current_date != last_notified_date:
                    last_notified_date = current_date
                    notified_safety = False
                
                safety_ok = True
                block_reason = ""
                
                if daily_dd >= config.MAX_DAILY_DRAWDOWN_PCT:
                    safety_ok = False
                    block_reason = f"Drawdown ngay dat {daily_dd:.2f}% (Gioi han {config.MAX_DAILY_DRAWDOWN_PCT}%)"
                    
                if losses >= config.MAX_CONSECUTIVE_LOSSES:
                    safety_ok = False
                    block_reason = f"Thua lien tiep {losses} lenh (Gioi han {config.MAX_CONSECUTIVE_LOSSES})"
                    
                positions = mt5.positions_get(magic=config.MAGIC_NUMBER)
                if positions is not None and len(positions) >= config.MAX_OPEN_POSITIONS:
                    safety_ok = False
                    block_reason = f"Dat gioi han {len(positions)}/ {config.MAX_OPEN_POSITIONS} lenh mo dong thoi"
                
                if not safety_ok:
                    now_str = datetime.now().strftime('%H:%M:%S')
                    print(f"[{now_str}] ⏸️ Tam ngung quet tin hieu moi: {block_reason}")
                    
                    if not notified_safety:
                        notifier.send_telegram_message(
                            f"⚠️ <b>CẢNH BÁO AN TOÀN BOT</b> ⚠️\n\n"
                            f"🤖 Bot tạm ngưng quét tín hiệu mới vì lý do:\n"
                            f"❌ <b>Lý do:</b> {block_reason}\n"
                            f"⚙️ Lệnh đang chạy (nếu có) vẫn được quản lý dời SL/Partial TP bình thường."
                        )
                        notified_safety = True
                
                # 2. Quét tín hiệu cho từng cặp giao dịch nếu các điều kiện an toàn đều thỏa mãn
                if safety_ok:
                    for sym, actual_sym in actual_symbols.items():
                        # Kiểm tra xem cặp tiền này đã có lệnh đang mở hay chưa
                        sym_positions = mt5.positions_get(symbol=actual_sym, magic=config.MAGIC_NUMBER)
                        if sym_positions is not None and len(sym_positions) > 0:
                            now_str = datetime.now().strftime('%H:%M:%S')
                            print(f"[{now_str}] [{actual_sym}] Da co lenh mo. Bo qua quet tin hieu moi.")
                            continue
                            
                        df_h1 = data_provider.get_rates(actual_sym, 'H1', 300)
                        df_m15 = data_provider.get_rates(actual_sym, 'M15', 300)
                    
                        if df_h1 is not None and df_m15 is not None:
                            current_candle_time = df_m15['time'].iloc[-1]
                            
                            if current_candle_time != last_sent_candle_times[sym]:
                                # Phân tích theo chiến lược
                                signal, skip_reason = strategy.analyze_market(sym, df_h1, df_m15)
                                
                                if signal is not None:
                                    print(f"🚀 PHÁT HIỆN TÍN HIỆU GIAO DỊCH [{actual_sym}]: {signal['action']} tại {signal['entry']:.5f}")
                                    
                                    # Giao dịch tự động nếu bật chế độ AUTO_TRADE
                                    if config.AUTO_TRADE:
                                        success, volume, ticket_or_err = execute_auto_trade(
                                            actual_sym, signal['action'], signal['sl'], signal['tp']
                                        )
                                        if success:
                                            signal['executed'] = True
                                            signal['volume'] = volume
                                            signal['ticket'] = ticket_or_err
                                            
                                            # Ghi trạng thái vị thế mới vào JSON
                                            states = load_position_states()
                                            states[str(ticket_or_err)] = {
                                                "original_sl": signal['sl'],
                                                "original_tp": signal['tp'],
                                                "entry_price": signal['entry'],
                                                "risk_distance": abs(signal['entry'] - signal['sl']),
                                                "partial_taken": False,
                                                "be_moved": False
                                            }
                                            save_position_states(states)
                                        else:
                                            signal['executed'] = False
                                            signal['err_desc'] = str(ticket_or_err)
                                            # Gửi thông báo lỗi vào lệnh
                                            notifier.send_execution_error_notification(sym, signal['action'], str(ticket_or_err))
                                            
                                    # Gửi thông báo tín hiệu/kết quả vào lệnh lên Telegram
                                    notifier.send_signal_notification(signal)
                                    last_sent_candle_times[sym] = current_candle_time
                                else:
                                    now_str = datetime.now().strftime('%H:%M:%S')
                                    # Trả log ngắn gọn lên console hiển thị rõ lý do bỏ qua lệnh
                                    print(f"[{now_str}] Đang quét {actual_sym} | Nến {current_candle_time} | {skip_reason}")
                                    last_sent_candle_times[sym] = current_candle_time
                            else:
                                pass # Tránh spam log nến cũ
                            
                # Tính thời gian chờ tới nến M15 tiếp theo
                sleep_seconds = get_seconds_until_next_m15()
                next_time_str = (datetime.now() + timedelta(seconds=sleep_seconds)).strftime('%H:%M:%S')
                print(f"============================================================")
                print(f"Đang nghỉ {sleep_seconds} giây... Lượt quét tiếp theo lúc: {next_time_str}")
                print(f"============================================================")
                time.sleep(sleep_seconds)
                
            except Exception as e:
                print(f"\n[Lỗi Vòng Lặp Chính] {e}")
                time.sleep(15)
                
    except KeyboardInterrupt:
        print("\nBot đã dừng bởi người dùng.")
    finally:
        data_provider.shutdown_mt5()
if __name__ == "__main__":
    main()
