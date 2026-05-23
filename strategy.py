from datetime import datetime, timedelta
import indicators
import config
def get_vietnam_time(dt):
    """
    Quy đổi thời gian UTC (GMT+0) sang giờ Việt Nam (UTC+7).
    Do pandas DataFrame ['time'] được chuyển từ Unix timestamp của MT5 (luôn là UTC),
    nên ta chỉ cần cộng 7 tiếng để quy đổi sang giờ Việt Nam.
    """
    return dt + timedelta(hours=7)
def find_overlapping_fvg(price, fvgs, trend):
    """Kiểm tra xem giá hiện tại có nằm trong vùng FVG hoạt động nào không."""
    for fvg in fvgs:
        if trend == 'UPTREND' and fvg['type'] == 'BULLISH':
            if fvg['bottom'] <= price <= fvg['top']:
                return True, fvg
        elif trend == 'DOWNTREND' and fvg['type'] == 'BEARISH':
            if fvg['bottom'] <= price <= fvg['top']:
                return True, fvg
    return False, None
def find_overlapping_ob(price, obs, trend):
    """Kiểm tra xem giá hiện tại có nằm trong vùng Order Block (OB) hoạt động nào không."""
    for ob in obs:
        if trend == 'UPTREND' and ob['type'] == 'BULLISH':
            if ob['bottom'] <= price <= ob['top']:
                return True, ob
        elif trend == 'DOWNTREND' and ob['type'] == 'BEARISH':
            if ob['bottom'] <= price <= ob['top']:
                return True, ob
    return False, None
def find_h1_tp_target(trend, current_price, swing_highs_h1, swing_lows_h1):
    """
    Xác định điểm Take Profit (TP) trên H1.
    - UPTREND: Đỉnh gần nhất hoặc vùng cản cao hơn giá hiện tại.
    - DOWNTREND: Đáy gần nhất hoặc vùng hỗ trợ thấp hơn giá hiện tại.
    """
    if trend == 'UPTREND':
        # Tìm đỉnh H1 gần nhất cao hơn giá hiện tại
        for sh in reversed(swing_highs_h1):
            if sh['price'] > current_price:
                return sh['price']
        # Fallback nếu không có đỉnh nào cao hơn (giá đang phá đỉnh thời đại)
        return current_price + 15.0 # TP mặc định là +15 USD
    else: # DOWNTREND
        # Tìm đáy H1 gần nhất thấp hơn giá hiện tại
        for sl in reversed(swing_lows_h1):
            if sl['price'] < current_price:
                return sl['price']
        # Fallback
        return current_price - 15.0 # TP mặc định là -15 USD
def analyze_market(symbol, df_h1, df_m15):
    """
    Phân tích toàn bộ chiến lược giao dịch:
    1. Lọc phiên giao dịch
    2. Tính EMA
    3. Xác định cấu trúc Swing High/Low
    4. Xác định xu hướng H1 và M15 (và lọc Sideway)
    5. Kiểm tra sự đồng bộ xu hướng
    6. Tính Fibo, FVG, OB trên M15 để tìm điểm vào lệnh
    7. Kiểm tra các yếu tố hợp lưu
    8. Tính SL (H1 Swing) và TP (H1 Swing) và kiểm tra tỷ lệ RR >= 1.5
    """
    # Bước 1: Lọc phiên giao dịch theo giờ Việt Nam (UTC+7)
    current_time = df_m15['time'].iloc[-1]
    if isinstance(current_time, str):
        try:
            dt = datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                dt = datetime.strptime(current_time, '%Y-%m-%d %H:%M')
            except ValueError:
                dt = datetime.now()
    else:
        dt = current_time
        
    # Quy đổi giờ sàn MT5 sang giờ Việt Nam (UTC+7)
    vn_time = get_vietnam_time(dt)
    hour = vn_time.hour
    
    if not (config.SESSION_START_HOUR <= hour <= config.SESSION_END_HOUR):
        # Trả về None cùng với lý do ngoài giờ giao dịch
        return None, f"Ngoài giờ giao dịch ({config.SESSION_START_HOUR}h-{config.SESSION_END_HOUR}h UTC+7)"
        
    # Lọc ngày trong tuần dựa trên giờ Việt Nam: Chỉ mở vị thế từ thứ Hai (0) đến thứ Năm (3).
    # Bỏ qua thứ Sáu (4) để tránh biến động cuối tuần.
    weekday = vn_time.weekday()
    if weekday >= 4:
        return None, "Ngoài ngày giao dịch (Chỉ giao dịch thứ 2 đến thứ 5)"
        
    # Bước 2: Tính chỉ báo ATR trên H1 làm buffer
    df_h1 = indicators.calculate_atr(df_h1)
    
    # Bộ lọc biến động: Nếu ATR hiện tại vượt quá 2 lần trung bình 20 kỳ -> bỏ qua lệnh (Spike tin tức)
    if len(df_h1) >= 20:
        atr_current = df_h1['atr'].iloc[-1]
        atr_mean = df_h1['atr'].iloc[-20:].mean()
        if atr_current > atr_mean * 2.0:
            reason = f"Thị trường biến động lớn (ATR {atr_current:.2f} > 2x ATR TB {atr_mean:.2f})"
            print(f"[{symbol.upper()}] Tin hieu bi bo qua: {reason}")
            return None, reason
            
    # Bước 3: Tìm Swings
    sh_h1, sl_h1 = indicators.find_swings(df_h1, left=4, right=2)
    sh_m15, sl_m15 = indicators.find_swings(df_m15, left=4, right=2)
    
    # Bước 4: Xác định xu hướng và lọc Sideways
    trend_h1 = indicators.get_market_trend(df_h1, sh_h1, sl_h1)
    trend_m15 = indicators.get_market_trend(df_m15, sh_m15, sl_m15)
    
    print(f"[{symbol.upper()}] Xu huong H1: {trend_h1} | Xu huong M15: {trend_m15}")
    
    # Điều kiện đủ 1: Khung H1 phải có xu hướng rõ ràng (không được đi ngang - SIDEWAYS)
    if trend_h1 == 'SIDEWAYS':
        reason = "Xu hướng H1 đi ngang (Sideways)"
        print(f"[{symbol.upper()}] Tin hieu bi bo qua: {reason}")
        return None, reason
        
    trend = trend_h1 # Bias chu dao dua vao khung H1
    
    current_price = df_m15['close'].iloc[-1]
    
    # Bước 5: Tính toán Fibonacci trên M15 của con sóng đẩy gần nhất
    fibs = indicators.calculate_fibonacci_zones(trend, sh_m15, sl_m15)
    if not fibs:
        reason = "Thiếu dữ liệu Swing để tính Fibonacci"
        print(f"[{symbol.upper()}] {reason}")
        return None, reason
        
    fib_05 = fibs[0.5]
    fib_0618 = fibs[0.618]
    fib_0786 = fibs[0.786]
    
    # Điều kiện đủ 2: Giá phải nằm trong vùng Fibonacci thoái lui [0.5 - 0.786]
    in_fib_zone = False
    if trend == 'UPTREND':
        in_fib_zone = fib_0786 <= current_price <= fib_05
    else: # DOWNTREND
        in_fib_zone = fib_05 <= current_price <= fib_0786
        
    if not in_fib_zone:
        reason = f"Giá nằm ngoài vùng Fibonacci [0.5 - 0.786] (Giá: {current_price:.5f})"
        print(f"[{symbol.upper()}] {reason}")
        return None, reason
        
    # Bước 6: Tìm FVG và OB trên M15 để kiểm tra hợp lưu
    fvgs = indicators.find_fvgs(df_m15, lookback=40)
    obs = indicators.find_order_blocks(df_m15, sh_m15, sl_m15, lookback=100)
    
    # Bước 7: Kiểm tra hợp lưu (Confluence)
    in_fvg, matched_fvg = find_overlapping_fvg(current_price, fvgs, trend)
    in_ob, matched_ob = find_overlapping_ob(current_price, obs, trend)
    
    confluences = []
    if in_fvg:
        confluences.append(f"Vùng FVG ({matched_fvg['bottom']:.5f} - {matched_fvg['top']:.5f})")
    if in_ob:
        confluences.append(f"Vùng Order Block ({matched_ob['bottom']:.5f} - {matched_ob['top']:.5f})")
        
    if not confluences:
        reason = "Không có hợp lưu FVG/OB tại vùng Fibonacci"
        print(f"[{symbol.upper()}] Tin hieu bi bo qua: {reason}")
        return None, reason
        
    # Bước 8: Xác định Stop Loss (SL) và Take Profit (TP) dựa trên cấu trúc H1
    atr_val = df_h1['atr'].iloc[-1] if 'atr' in df_h1.columns else (current_price * 0.001)
    # Đặt khoảng đệm (buffer) SL bằng 0.5 * ATR
    atr_buffer = atr_val * 0.5
    
    if trend == 'UPTREND':
        # SL là đáy Swing Low H1 gần nhất trừ thêm ATR buffer
        base_sl = sl_h1[-1]['price'] if sl_h1 else df_h1['low'].iloc[-20:].min()
        sl = base_sl - atr_buffer
        if sl >= current_price:
            sl = df_m15['low'].iloc[-15:].min() - (current_price * 0.0005)
            
        tp = find_h1_tp_target(trend, current_price, sh_h1, sl_h1)
        risk = current_price - sl
        reward = tp - current_price
    else: # DOWNTREND
        # SL là đỉnh Swing High H1 gần nhất cộng thêm ATR buffer
        base_sl = sh_h1[-1]['price'] if sh_h1 else df_h1['high'].iloc[-20:].max()
        sl = base_sl + atr_buffer
        if sl <= current_price:
            sl = df_m15['high'].iloc[-15:].max() + (current_price * 0.0005)
            
        tp = find_h1_tp_target(trend, current_price, sh_h1, sl_h1)
        risk = sl - current_price
        reward = current_price - tp
        
    if risk <= 0:
        reason = "Khoảng cách SL không hợp lệ"
        print(f"[{symbol.upper()}] Tin hieu bi bo qua: {reason}")
        return None, reason
        
    rr = reward / risk
    
    # Điều kiện đủ 3: Tỉ lệ RR phải đạt trên 1.5
    if rr < config.MIN_RR_RATIO:
        reason = f"Tỷ lệ RR ({rr:.2f}) dưới mức tối thiểu {config.MIN_RR_RATIO} (SL: {sl:.5f}, TP: {tp:.5f})"
        print(f"[{symbol.upper()}] Tin hieu bi bo qua: {reason}")
        return None, reason
        
    # Chuẩn bị thông tin tín hiệu trả về
    signal_info = {
        'symbol': symbol,
        'action': 'BUY' if trend == 'UPTREND' else 'SELL',
        'entry': current_price,
        'sl': sl,
        'tp': tp,
        'rr': rr,
        'confluences': confluences,
        'fib_levels': {
            '0.5': fib_05,
            '0.618': fib_0618,
            '0.786': fib_0786
        },
        'time': df_m15['time'].iloc[-1]
    }
    
    return signal_info, None
