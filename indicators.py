import pandas as pd
import numpy as np
def find_swings(df, left=4, right=2):
    """
    Xác định các điểm Swing High và Swing Low.
    Một cây nến tại index i là Swing High nếu High của nó cao nhất trong khoảng [i-left, i+right].
    Một cây nến tại index i là Swing Low nếu Low của nó thấp nhất trong khoảng [i-left, i+right].
    """
    highs = df['high'].values
    lows = df['low'].values
    times = df['time'].values
    closes = df['close'].values
    opens = df['open'].values
    
    swing_highs = []
    swing_lows = []
    
    for i in range(left, len(df) - right):
        # Kiểm tra Swing High
        is_high = True
        for j in range(i - left, i + right + 1):
            if highs[i] < highs[j]:
                is_high = False
                break
        if is_high:
            swing_highs.append({
                'index': i,
                'time': times[i],
                'price': highs[i],
                'close': closes[i],
                'open': opens[i],
                'type': 'SH'
            })
            
        # Kiểm tra Swing Low
        is_low = True
        for j in range(i - left, i + right + 1):
            if lows[i] > lows[j]:
                is_low = False
                break
        if is_low:
            swing_lows.append({
                'index': i,
                'time': times[i],
                'price': lows[i],
                'close': closes[i],
                'open': opens[i],
                'type': 'SL'
            })
            
    return swing_highs, swing_lows
def get_market_trend(df, swing_highs, swing_lows):
    """
    Xác định xu hướng thị trường dựa trên cấu trúc đỉnh/đáy Price Action (HH/HL hoặc LH/LL).
    
    - UPTREND (HH-HL): Phá đỉnh sh_new['price'] là BOS (Break of Structure - tiếp diễn UPTREND).
      Chỉ khi giá đóng cửa dưới sl_new['price'] (CHoCH - gãy cấu trúc) mới trả về SIDEWAYS.
    - DOWNTREND (LH-LL): Phá đáy sl_new['price'] là BOS (Break of Structure - tiếp diễn DOWNTREND).
      Chỉ khi giá đóng cửa trên sh_new['price'] (CHoCH - gãy cấu trúc) mới trả về SIDEWAYS.
    """
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return 'SIDEWAYS'
        
    sh_new, sh_old = swing_highs[-1], swing_highs[-2]
    sl_new, sl_old = swing_lows[-1], swing_lows[-2]
    
    current_close = df['close'].iloc[-1]
    
    is_hh_hl = (sh_new['price'] > sh_old['price']) and (sl_new['price'] > sl_old['price'])
    is_ll_lh = (sl_new['price'] < sl_old['price']) and (sh_new['price'] < sh_old['price'])
    
    if is_hh_hl:
        # UPTREND: Phá đỉnh sh_new['price'] là BOS -> UPTREND tiếp diễn.
        # Chỉ báo SIDEWAYS khi đóng cửa dưới đáy sl_new['price'] (CHoCH).
        if current_close < sl_new['price']:
            return 'SIDEWAYS'
        return 'UPTREND'
        
    elif is_ll_lh:
        # DOWNTREND: Phá đáy sl_new['price'] là BOS -> DOWNTREND tiếp diễn.
        # Chỉ báo SIDEWAYS khi đóng cửa trên đỉnh sh_new['price'] (CHoCH).
        if current_close > sh_new['price']:
            return 'SIDEWAYS'
        return 'DOWNTREND'
    
    return 'SIDEWAYS'
def calculate_fibonacci_zones(trend, swing_highs, swing_lows):
    """
    Tính toán các mức Fibonacci 0.5, 0.618, 0.786 từ con sóng đẩy gần nhất.
    Trong UPTREND: Kéo từ đáy lên đỉnh (đáy phải đứng trước đỉnh).
    Trong DOWNTREND: Kéo từ đỉnh xuống đáy (đỉnh phải đứng trước đáy).
    """
    if len(swing_highs) == 0 or len(swing_lows) == 0:
        return {}
        
    fibs = {}
    if trend == 'UPTREND':
        # Tìm đỉnh gần nhất
        sh_latest = swing_highs[-1]
        # Tìm đáy gần nhất đứng TRƯỚC đỉnh này
        sl_before = None
        for sl in reversed(swing_lows):
            if sl['index'] < sh_latest['index']:
                sl_before = sl
                break
        if not sl_before:
            return {}
            
        high_p = sh_latest['price']
        low_p = sl_before['price']
        diff = high_p - low_p
        if diff <= 0:
            return {}
            
        fibs[0.5] = high_p - 0.5 * diff
        fibs[0.618] = high_p - 0.618 * diff
        fibs[0.786] = high_p - 0.786 * diff
        
    elif trend == 'DOWNTREND':
        # Tìm đáy gần nhất
        sl_latest = swing_lows[-1]
        # Tìm đỉnh gần nhất đứng TRƯỚC đáy này
        sh_before = None
        for sh in reversed(swing_highs):
            if sh['index'] < sl_latest['index']:
                sh_before = sh
                break
        if not sh_before:
            return {}
            
        high_p = sh_before['price']
        low_p = sl_latest['price']
        diff = high_p - low_p
        if diff <= 0:
            return {}
            
        fibs[0.5] = low_p + 0.5 * diff
        fibs[0.618] = low_p + 0.618 * diff
        fibs[0.786] = low_p + 0.786 * diff
        
    return fibs
def find_fvgs(df, lookback=40):
    """
    Tìm các khoảng trống giá trị hợp lý FVG (Fair Value Gap) chưa bị lấp.
    Trả về danh sách các FVG hoạt động kèm theo vùng giá.
    """
    fvgs = []
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    times = df['time'].values
    
    # Quét trong khoảng lookback gần đây
    start_idx = max(1, len(df) - lookback)
    for i in range(start_idx, len(df) - 1):
        # Bullish FVG: Low của nến 3 > High của nến 1 (nến 2 là nến bật mạnh)
        # Nến 1: i-1, Nến 2: i, Nến 3: i+1
        if i > 0 and i < len(df) - 1:
            if lows[i+1] > highs[i-1]:
                # Vùng FVG từ highs[i-1] đến lows[i+1]
                fvg_top = lows[i+1]
                fvg_bottom = highs[i-1]
                
                # Kiểm tra xem FVG này đã bị lấp bởi các nến sau đó chưa (từ i+2 đến hiện tại)
                is_mitigated = False
                for k in range(i+2, len(df)):
                    if lows[k] <= fvg_bottom: # Bị lấp hoàn toàn
                        is_mitigated = True
                        break
                
                if not is_mitigated:
                    fvgs.append({
                        'type': 'BULLISH',
                        'top': fvg_top,
                        'bottom': fvg_bottom,
                        'time': times[i],
                        'index': i
                    })
                    
            # Bearish FVG: High của nến 3 < Low của nến 1
            elif highs[i+1] < lows[i-1]:
                fvg_top = lows[i-1]
                fvg_bottom = highs[i+1]
                
                # Kiểm tra lấp
                is_mitigated = False
                for k in range(i+2, len(df)):
                    if highs[k] >= fvg_top: # Bị lấp hoàn toàn
                        is_mitigated = True
                        break
                        
                if not is_mitigated:
                    fvgs.append({
                        'type': 'BEARISH',
                        'top': fvg_top,
                        'bottom': fvg_bottom,
                        'time': times[i],
                        'index': i
                    })
    return fvgs
def find_order_blocks(df, swing_highs, swing_lows, lookback=100):
    """
    Xác định các vùng Order Block (OB) chưa bị giảm thiểu (unmitigated).
    - Bullish OB: Cây nến giảm (bearish) cuối cùng trước khi giá tăng mạnh phá đỉnh gần nhất.
    - Bearish OB: Cây nến tăng (bullish) cuối cùng trước khi giá giảm mạnh phá đáy gần nhất.
    """
    obs = []
    if len(df) < lookback:
        return obs
        
    opens = df['open'].values
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    times = df['time'].values
    
    # 1. Tìm Bullish OB
    # Quét qua các Swing Low gần đây.
    # Nến tại Swing Low thường là nến giảm cuối cùng trước đợt tăng.
    for sl in swing_lows:
        idx = sl['index']
        # Chỉ xét các swing trong khoảng lookback
        if idx < len(df) - lookback:
            continue
            
        # Nến tại idx phải là nến giảm (hoặc nến trước đó một chút)
        # Tìm nến giảm thực sự xung quanh Swing Low
        ob_idx = idx
        while ob_idx >= 0 and closes[ob_idx] > opens[ob_idx]:
            ob_idx -= 1
            
        if ob_idx < 0:
            continue
            
        ob_top = highs[ob_idx]
        ob_bottom = lows[ob_idx]
        
        # Kiểm tra xem OB này đã bị giá giảm xuống dưới và đóng cửa xuyên qua (mitigated) chưa
        is_mitigated = False
        for k in range(ob_idx + 1, len(df)):
            if closes[k] < ob_bottom:
                is_mitigated = True
                break
                
        if not is_mitigated:
            obs.append({
                'type': 'BULLISH',
                'top': ob_top,
                'bottom': ob_bottom,
                'time': times[ob_idx],
                'index': ob_idx
            })
            
    # 2. Tìm Bearish OB
    for sh in swing_highs:
        idx = sh['index']
        if idx < len(df) - lookback:
            continue
            
        ob_idx = idx
        while ob_idx >= 0 and closes[ob_idx] < opens[ob_idx]:
            ob_idx -= 1
            
        if ob_idx < 0:
            continue
            
        ob_top = highs[ob_idx]
        ob_bottom = lows[ob_idx]
        
        # Kiểm tra xem OB đã bị giá đóng cửa vượt lên trên (mitigated) chưa
        is_mitigated = False
        for k in range(ob_idx + 1, len(df)):
            if closes[k] > ob_top:
                is_mitigated = True
                break
                
        if not is_mitigated:
            obs.append({
                'type': 'BEARISH',
                'top': ob_top,
                'bottom': ob_bottom,
                'time': times[ob_idx],
                'index': ob_idx
            })
            
    return obs
def get_liquidity_swept_sl_tp(df, swing_lows, swing_highs):
    """
    Xác định Stop Loss là đáy/đỉnh gần nhất trên khung M15 đã được quét thanh khoản.
    
    - Đáy quét thanh khoản (Liquidity Swept Low) cho Buy:
      Là một Swing Low có giá trị thấp nhất (Low) thấp hơn đáy (Swing Low) trước đó của nó, 
      nhưng giá rút chân ngược lên (nến sau đó hoặc chính nó có giá đóng cửa nằm trên đáy cũ),
      chứng tỏ đã quét stoploss nằm dưới đáy cũ rồi đi lên.
      
    - Đỉnh quét thanh khoản (Liquidity Swept High) cho Sell:
      Là một Swing High có giá trị cao nhất (High) cao hơn đỉnh (Swing High) trước đó của nó,
      nhưng rút chân đóng cửa dưới đỉnh cũ.
    """
    swept_low = None
    swept_high = None
    
    # 1. Tìm đáy quét thanh khoản gần nhất
    if len(swing_lows) >= 2:
        for idx in range(len(swing_lows) - 1, 0, -1):
            curr_sl = swing_lows[idx]
            prev_sl = swing_lows[idx - 1]
            
            # Nếu đáy hiện tại thấp hơn đáy trước -> Đã lấy thanh khoản của đáy trước
            if curr_sl['price'] < prev_sl['price']:
                # Đảm bảo giá đóng cửa của nến đáy hiện tại nằm trên đáy trước, hoặc nến tiếp theo đóng cửa trên đáy trước (rút chân quét thanh khoản)
                curr_idx = curr_sl['index']
                # Xem xét giá đóng cửa của nến đó và nến ngay sau
                closes_to_check = df['close'].iloc[curr_idx : min(curr_idx + 3, len(df))]
                if any(c > prev_sl['price'] for c in closes_to_check):
                    swept_low = curr_sl['price']
                    break
        
        # Fallback nếu không có quét thanh khoản rõ ràng, lấy đáy thấp nhất gần nhất làm SL an toàn
        if swept_low is None:
            swept_low = swing_lows[-1]['price']
            
    # 2. Tìm đỉnh quét thanh khoản gần nhất
    if len(swing_highs) >= 2:
        for idx in range(len(swing_highs) - 1, 0, -1):
            curr_sh = swing_highs[idx]
            prev_sh = swing_highs[idx - 1]
            
            # Nếu đỉnh hiện tại cao hơn đỉnh trước -> Đã lấy thanh khoản của đỉnh trước
            if curr_sh['price'] > prev_sh['price']:
                curr_idx = curr_sh['index']
                closes_to_check = df['close'].iloc[curr_idx : min(curr_idx + 3, len(df))]
                if any(c < prev_sh['price'] for c in closes_to_check):
                    swept_high = curr_sh['price']
                    break
                    
        # Fallback
        if swept_high is None:
            swept_high = swing_highs[-1]['price']
            
    return swept_low, swept_high
def calculate_atr(df, period=14):
    """Tính toán chỉ báo ATR (Average True Range) trên DataFrame."""
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    df['atr'] = atr
    return df
