from datetime import datetime, timedelta
import math
import indicators
import config
import pandas as pd

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

def find_h1_tp_target(trend, current_price, swing_highs_h1, swing_lows_h1, sh_m15=None, sl_m15=None, atr_h1=0.0):
    """
    Xác định điểm Take Profit (TP) trên H1 hoặc theo Fibonacci Extension M15 khi giá phá đỉnh/đáy lịch sử.
    - UPTREND: Đỉnh gần nhất cao hơn giá hiện tại. Nếu phá đỉnh lịch sử: dùng Fib Extension 1.272 sóng M15 hoặc 2.0 * ATR_H1.
    - DOWNTREND: Đáy gần nhất thấp hơn giá hiện tại. Nếu phá đáy lịch sử: dùng Fib Extension 1.272 sóng M15 hoặc 2.0 * ATR_H1.
    """
    if trend == 'UPTREND':
        # Tìm đỉnh H1 gần nhất cao hơn giá hiện tại
        for sh in reversed(swing_highs_h1):
            if sh['price'] > current_price:
                return sh['price']
        
        # Fallback 1: Fibonacci Extension 1.272 của con sóng M15 gần nhất
        if sh_m15 and sl_m15:
            sh_last = sh_m15[-1]
            sl_before = None
            for sl_item in reversed(sl_m15):
                if sl_item['index'] < sh_last['index']:
                    sl_before = sl_item
                    break
            if sl_before:
                diff = sh_last['price'] - sl_before['price']
                if diff > 0:
                    fib_ext_tp = sh_last['price'] + 0.272 * diff
                    if fib_ext_tp > current_price:
                        return fib_ext_tp

        # Fallback 2: 2.0 * ATR_H1 (hoặc +15.0 USD nếu không có ATR)
        fallback_dist = (2.0 * atr_h1) if atr_h1 > 0 else 15.0
        return current_price + fallback_dist

    else: # DOWNTREND
        # Tìm đáy H1 gần nhất thấp hơn giá hiện tại
        for sl in reversed(swing_lows_h1):
            if sl['price'] < current_price:
                return sl['price']

        # Fallback 1: Fibonacci Extension 1.272 của con sóng M15 gần nhất
        if sl_m15 and sh_m15:
            sl_last = sl_m15[-1]
            sh_before = None
            for sh_item in reversed(sh_m15):
                if sh_item['index'] < sl_last['index']:
                    sh_before = sh_item
                    break
            if sh_before:
                diff = sh_before['price'] - sl_last['price']
                if diff > 0:
                    fib_ext_tp = sl_last['price'] - 0.272 * diff
                    if fib_ext_tp < current_price:
                        return fib_ext_tp

        # Fallback 2: 2.0 * ATR_H1 (hoặc -15.0 USD nếu không có ATR)
        fallback_dist = (2.0 * atr_h1) if atr_h1 > 0 else 15.0
        return current_price - fallback_dist

def analyze_market(symbol, df_h1, df_m15, current_spread=0.0):
    """
    Phân tích toàn bộ chiến lược giao dịch trên nến đã đóng iloc[-2] (tránh Repainting/Look-ahead bias):
    1. Lọc phiên giao dịch và lọc Spread trước khi vào lệnh
    2. Tính ATR trên H1 và M15
    3. Xác định cấu trúc Swing High/Low
    4. Xác định xu hướng H1 và M15
    5. Kiểm tra giá iloc[-2] trong vùng Fibonacci pullback M15
    6. Kiểm tra các yếu tố hợp lưu FVG/OB
    7. Tính SL theo cấu trúc M15 (OB + Swing M15 +/- 0.5*ATR_M15) và TP theo H1/Fib Extension
    8. Kiểm tra tỷ lệ RR và các bộ lọc rủi ro
    """
    if len(df_m15) < 3 or len(df_h1) < 20:
        return None, "Dữ liệu nến không đủ để phân tích"

    # Bước 1: Lọc phiên giao dịch theo giờ Việt Nam (UTC+7) dựa trên nến đã đóng iloc[-2]
    closed_idx = -2
    current_time = df_m15['time'].iloc[closed_idx]
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
        
    vn_time = get_vietnam_time(dt)
    hour = vn_time.hour
    
    if not (config.SESSION_START_HOUR <= hour <= config.SESSION_END_HOUR):
        return None, f"Ngoài giờ giao dịch ({config.SESSION_START_HOUR}h-{config.SESSION_END_HOUR}h UTC+7)"
        
    weekday = vn_time.weekday()
    if config.ALLOW_FRIDAY_TRADING:
        if weekday >= 5:
            return None, "Ngoài ngày giao dịch (Chỉ giao dịch thứ 2 đến thứ 6)"
    else:
        if weekday >= 4:
            return None, "Ngoài ngày giao dịch (Chỉ giao dịch thứ 2 đến thứ 5)"

    # Lọc Spread trước khi vào lệnh
    max_allowed_spread = getattr(config, 'MAX_ALLOWED_SPREAD', 30.0)
    if current_spread > 0 and current_spread > max_allowed_spread:
        reason = f"Spread quá cao ({current_spread:.1f} > {max_allowed_spread:.1f})"
        print(f"[{symbol.upper()}] Tin hieu bi bo qua: {reason}")
        return None, reason
        
    # Bước 2: Tính chỉ báo ATR trên H1 và M15 làm buffer
    df_h1 = indicators.calculate_atr(df_h1)
    df_m15 = indicators.calculate_atr(df_m15)
    
    # Bộ lọc biến động ATR spike trên H1
    if len(df_h1) >= 20:
        atr_current = df_h1['atr'].iloc[-1]
        atr_mean = df_h1['atr'].iloc[-20:].mean()
        if atr_current > atr_mean * config.ATR_SPIKE_FILTER_MULT:
            reason = f"Thị trường biến động lớn (ATR {atr_current:.2f} > {config.ATR_SPIKE_FILTER_MULT}x ATR TB {atr_mean:.2f})"
            print(f"[{symbol.upper()}] Tin hieu bi bo qua: {reason}")
            return None, reason
            
    # Bước 3: Tìm Swings
    sh_h1, sl_h1 = indicators.find_swings(df_h1, left=4, right=2)
    sh_m15, sl_m15 = indicators.find_swings(df_m15, left=4, right=2)
    
    # Bước 4: Xác định xu hướng và lọc Sideways
    trend_h1 = indicators.get_market_trend(df_h1, sh_h1, sl_h1)
    trend_m15 = indicators.get_market_trend(df_m15, sh_m15, sl_m15)
    
    print(f"[{symbol.upper()}] Xu huong H1: {trend_h1} | Xu huong M15: {trend_m15}")
    
    if trend_h1 == 'SIDEWAYS':
        reason = "Xu hướng H1 đi ngang (Sideways)"
        print(f"[{symbol.upper()}] Tin hieu bi bo qua: {reason}")
        return None, reason
    
    atr_for_trend = df_h1['atr'].iloc[-1] if 'atr' in df_h1.columns else 0.0
    trend_step_atr = 0.0
    if atr_for_trend and atr_for_trend > 0 and len(sh_h1) >= 2 and len(sl_h1) >= 2:
        if trend_h1 == 'UPTREND':
            hh_step = (sh_h1[-1]['price'] - sh_h1[-2]['price']) / atr_for_trend
            hl_step = (sl_h1[-1]['price'] - sl_h1[-2]['price']) / atr_for_trend
            trend_step_atr = min(hh_step, hl_step)
        elif trend_h1 == 'DOWNTREND':
            ll_step = (sl_h1[-2]['price'] - sl_h1[-1]['price']) / atr_for_trend
            lh_step = (sh_h1[-2]['price'] - sh_h1[-1]['price']) / atr_for_trend
            trend_step_atr = min(ll_step, lh_step)
    
    if trend_step_atr < config.TREND_MIN_STEP_ATR:
        reason = f"Cấu trúc H1 yếu (step {trend_step_atr:.2f} ATR < {config.TREND_MIN_STEP_ATR:.2f})"
        return None, reason
        
    trend = trend_h1 # Bias chủ đạo dựa vào khung H1
    
    # Lấy giá của cây nến M15 đã đóng cửa gần nhất (iloc[-2]) để tránh Repainting
    current_price = df_m15['close'].iloc[-2]
    current_open = df_m15['open'].iloc[-2]
    current_high = df_m15['high'].iloc[-2]
    current_low = df_m15['low'].iloc[-2]
    prev_high = df_m15['high'].iloc[-3]
    prev_low = df_m15['low'].iloc[-3]
    
    # Bước 5: Tính toán Fibonacci trên M15 của con sóng đẩy gần nhất
    fibs = indicators.calculate_fibonacci_zones(trend, sh_m15, sl_m15)
    if not fibs:
        reason = "Thiếu dữ liệu Swing để tính Fibonacci"
        print(f"[{symbol.upper()}] {reason}")
        return None, reason
        
    fib_05 = fibs[0.5]
    fib_0618 = fibs[0.618]
    fib_0786 = fibs[0.786]
    
    in_fib_zone = False
    fib_lower = config.FIB_ENTRY_LOWER
    if trend == 'UPTREND':
        fib_lower_price = fibs[fib_lower] if fib_lower in fibs else fib_05
        in_fib_zone = fib_0786 <= current_price <= fib_lower_price
    else: # DOWNTREND
        fib_lower_price = fibs[fib_lower] if fib_lower in fibs else fib_05
        in_fib_zone = fib_lower_price <= current_price <= fib_0786
        
    if not in_fib_zone:
        reason = f"Giá nằm ngoài vùng Fibonacci [{fib_lower} - 0.786] (Giá: {current_price:.5f})"
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
    confluence_score = (1 if in_fvg else 0) + (1 if in_ob else 0)
        
    if not confluences:
        reason = "Không có hợp lưu FVG/OB tại vùng Fibonacci"
        print(f"[{symbol.upper()}] Tin hieu bi bo qua: {reason}")
        return None, reason
    if confluence_score < config.MIN_CONFLUENCE_SCORE:
        return None, f"Hợp lưu chưa đủ mạnh ({confluence_score} < {config.MIN_CONFLUENCE_SCORE})"
 
    # Xác nhận nến đảo chiều M15 (đánh giá trên nến đóng cửa iloc[-2] so với iloc[-3])
    if config.M15_CONFIRM_MODE == "none":
        confirm_ok = True
    else:
        body = abs(current_price - current_open)
        if trend == 'UPTREND':
            base_confirm = (current_price > current_open) and (current_price > prev_high)
            if config.M15_CONFIRM_MODE == "wick":
                lower_wick = min(current_open, current_price) - current_low
                confirm_ok = base_confirm and (lower_wick >= body * 0.5)
            else:
                confirm_ok = base_confirm
        else:
            base_confirm = (current_price < current_open) and (current_price < prev_low)
            if config.M15_CONFIRM_MODE == "wick":
                upper_wick = current_high - max(current_open, current_price)
                confirm_ok = base_confirm and (upper_wick >= body * 0.5)
            else:
                confirm_ok = base_confirm
    if not confirm_ok:
        return None, "Chưa có xác nhận đảo chiều M15 theo hướng H1"
        
    # Bước 8: Tính Stop Loss (SL) theo cấu trúc M15 (Order Block M15 & Swing Low/High M15 + 0.5*ATR_M15)
    atr_m15 = df_m15['atr'].iloc[-2] if ('atr' in df_m15.columns and not pd.isna(df_m15['atr'].iloc[-2])) else (current_price * 0.001)
    atr_h1 = df_h1['atr'].iloc[-1] if ('atr' in df_h1.columns and not pd.isna(df_h1['atr'].iloc[-1])) else (current_price * 0.001)
    atr_buffer = atr_m15 * 0.5
    
    if trend == 'UPTREND':
        # BUY: SL = min(Đáy Order Block M15, Swing Low M15 gần nhất) - (0.5 * ATR_M15)
        sl_m15_base = sl_m15[-1]['price'] if sl_m15 else df_m15['low'].iloc[-20:-1].min()
        if matched_ob and 'bottom' in matched_ob:
            base_sl = min(matched_ob['bottom'], sl_m15_base)
        else:
            base_sl = sl_m15_base
        sl = base_sl - atr_buffer
        if sl >= current_price:
            sl = current_price - (1.5 * atr_m15)
            
        tp = find_h1_tp_target(trend, current_price, sh_h1, sl_h1, sh_m15, sl_m15, atr_h1)
        risk = current_price - sl
        reward = tp - current_price
    else: # DOWNTREND
        # SELL: SL = max(Đỉnh Order Block M15, Swing High M15 gần nhất) + (0.5 * ATR_M15)
        sh_m15_base = sh_m15[-1]['price'] if sh_m15 else df_m15['high'].iloc[-20:-1].max()
        if matched_ob and 'top' in matched_ob:
            base_sl = max(matched_ob['top'], sh_m15_base)
        else:
            base_sl = sh_m15_base
        sl = base_sl + atr_buffer
        if sl <= current_price:
            sl = current_price + (1.5 * atr_m15)
            
        tp = find_h1_tp_target(trend, current_price, sh_h1, sl_h1, sh_m15, sl_m15, atr_h1)
        risk = sl - current_price
        reward = current_price - tp
        
    if risk <= 0:
        reason = "Khoảng cách SL không hợp lệ"
        print(f"[{symbol.upper()}] Tin hieu bi bo qua: {reason}")
        return None, reason
        
    risk_atr_mult = 0.0
    if atr_h1 > 0:
        risk_atr_mult = risk / atr_h1
        if risk_atr_mult > config.MAX_RISK_ATR_MULT:
            reason = f"SL quá rộng so với ATR ({risk_atr_mult:.2f}x > {config.MAX_RISK_ATR_MULT}x)"
            print(f"[{symbol.upper()}] Tin hieu bi bo qua: {reason}")
            return None, reason
        if risk_atr_mult < config.MIN_RISK_ATR_MULT:
            reason = f"SL quá hẹp so với ATR ({risk_atr_mult:.2f}x < {config.MIN_RISK_ATR_MULT}x)"
            print(f"[{symbol.upper()}] Tin hieu bi bo qua: {reason}")
            return None, reason
        
    rr = reward / risk
    
    if rr < config.MIN_RR_RATIO:
        reason = f"Tỷ lệ RR ({rr:.2f}) dưới mức tối thiểu {config.MIN_RR_RATIO} (SL: {sl:.5f}, TP: {tp:.5f})"
        print(f"[{symbol.upper()}] Tin hieu bi bo qua: {reason}")
        return None, reason
        
    if rr > config.MAX_RR_RATIO:
        reason = f"Tỷ lệ RR ({rr:.2f}) vượt quá ngưỡng chất lượng {config.MAX_RR_RATIO}"
        print(f"[{symbol.upper()}] Tin hieu bi bo qua: {reason}")
        return None, reason

    risk_mult = 1.0
    if config.ENABLE_QUALITY_RISK_SCALING:
        rr_sweet = 1.4 <= rr <= 2.2
        atr_sweet = (risk_atr_mult == 0.0) or (0.6 <= risk_atr_mult <= 2.2)
        is_high_quality = (confluence_score >= 2) and rr_sweet and atr_sweet
        if not is_high_quality:
            risk_mult = config.LOW_QUALITY_RISK_MULT
        
    # Chuẩn bị thông tin tín hiệu trả về
    signal_info = {
        'symbol': symbol,
        'action': 'BUY' if trend == 'UPTREND' else 'SELL',
        'entry': current_price,
        'sl': sl,
        'tp': tp,
        'rr': rr,
        'trend_step_atr': trend_step_atr,
        'risk_mult': risk_mult,
        'confluences': confluences,
        'fib_levels': {
            str(fib_lower): fibs.get(fib_lower, fib_05),
            '0.5': fib_05,
            '0.618': fib_0618,
            '0.786': fib_0786
        },
        'time': df_m15['time'].iloc[closed_idx]
    }
    
    return signal_info, None
