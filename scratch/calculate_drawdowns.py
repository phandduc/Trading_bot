import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

# Import bot modules
sys.path.append(r'C:\Users\Duc\.gemini\antigravity\scratch\xauusd_trading_bot')
import indicators
import strategy
import config
import data_provider

# MetaTrader 5 module
import MetaTrader5 as mt5

def run_drawdown_backtest():
    print("=== BAT DAU MO PHONG BACKTEST TINH MAX DRAWDOWN (180 NGAY) ===")
    if not data_provider.initialize_mt5():
        print("MetaTrader5 initialize failed")
        return
        
    symbols = ["XAUUSD", "GBPUSD"]
    data = {}
    
    for symbol in symbols:
        actual_sym = data_provider.get_actual_symbol(symbol)
        print(f"Loading data for {actual_sym}...")
        df_m15 = data_provider.get_rates(actual_sym, 'M15', 180 * 96)
        df_h1 = data_provider.get_rates(actual_sym, 'H1', 180 * 24)
        if df_m15 is not None and df_h1 is not None:
            data[symbol] = {
                'df_m15': df_m15,
                'df_h1': df_h1
            }
            print(f"Downloaded {len(df_h1)} H1 bars and {len(df_m15)} M15 bars for {symbol}.")
        else:
            print(f"Failed to load data for {symbol}")
            
    mt5.shutdown()
    
    if len(data) < 2:
        print("Not enough symbol data.")
        return
        
    # We will run a combined backtest on XAUUSD and GBPUSD together.
    # To run a combined backtest, we must process time chronologically.
    # We will merge the M15 bars of both symbols sorted by time.
    
    df_xau = data['XAUUSD']['df_m15'].copy()
    df_xau['symbol'] = 'XAUUSD'
    
    df_gbp = data['GBPUSD']['df_m15'].copy()
    df_gbp['symbol'] = 'GBPUSD'
    
    # Combine and sort by time
    combined_m15 = pd.concat([df_xau, df_gbp], ignore_index=True)
    combined_m15 = combined_m15.sort_values(by='time').reset_index(drop=True)
    
    # We will run the combined simulation for risk_pct = 1%, 2%, 3%
    results = {}
    
    for risk_pct in [0.01, 0.02, 0.03]:
        print(f"\n--- Simulating Combined Portfolio with Risk: {risk_pct*100}% ---")
        initial_balance = 10000.0
        balance = initial_balance
        peak = initial_balance
        max_drawdown = 0.0
        
        # Position states for active trades (can have active trade per symbol)
        active_trades = {
            'XAUUSD': None,
            'GBPUSD': None
        }
        
        trades = []
        
        # We need H1 historical data for lookups. Since we sorted by time, we can filter H1 data dynamically.
        h1_data = {
            'XAUUSD': data['XAUUSD']['df_h1'],
            'GBPUSD': data['GBPUSD']['df_h1']
        }
        
        # Keep track of balance history for drawdown calculation
        balance_history = [initial_balance]
        
        # Iterate over combined timeline
        # To avoid lookup issues, we'll keep track of indices of the raw dataframes
        raw_m15 = {
            'XAUUSD': data['XAUUSD']['df_m15'],
            'GBPUSD': data['GBPUSD']['df_m15']
        }
        
        for idx, row in combined_m15.iterrows():
            sym = row['symbol']
            current_time = row['time']
            current_close = row['close']
            current_high = row['high']
            current_low = row['low']
            
            # Find the corresponding index in raw_m15
            raw_df = raw_m15[sym]
            raw_idx_list = raw_df[raw_df['time'] == current_time].index
            if len(raw_idx_list) == 0:
                continue
            raw_idx = raw_idx_list[0]
            if raw_idx < 200:
                continue
                
            active_trade = active_trades[sym]
            
            # 1. Manage active trade for this symbol
            if active_trade is not None:
                risk_dist = active_trade['risk_distance']
                entry = active_trade['entry']
                
                # Check BE
                if not active_trade['be_moved']:
                    if active_trade['type'] == 'BUY':
                        if current_high >= entry + (risk_dist * 0.8):
                            active_trade['sl'] = entry
                            active_trade['be_moved'] = True
                    else:
                        if current_low <= entry - (risk_dist * 0.8):
                            active_trade['sl'] = entry
                            active_trade['be_moved'] = True
                            
                # Check Partial TP (PARTIAL_1.5)
                if not active_trade['partial_taken']:
                    partial_tp_dist = risk_dist * 1.5
                    if active_trade['type'] == 'BUY':
                        if current_high >= entry + partial_tp_dist:
                            realized_pnl = (active_trade['units'] / 2) * ( (entry + partial_tp_dist) - entry )
                            balance += realized_pnl
                            # Track drawdown
                            if balance > peak: peak = balance
                            dd = (peak - balance) / peak * 100.0
                            if dd > max_drawdown: max_drawdown = dd
                            
                            active_trade['partial_taken'] = True
                            active_trade['sl'] = entry
                            active_trade['be_moved'] = True
                    else:
                        if current_low <= entry - partial_tp_dist:
                            realized_pnl = (active_trade['units'] / 2) * ( entry - (entry - partial_tp_dist) )
                            balance += realized_pnl
                            
                            if balance > peak: peak = balance
                            dd = (peak - balance) / peak * 100.0
                            if dd > max_drawdown: max_drawdown = dd
                            
                            active_trade['partial_taken'] = True
                            active_trade['sl'] = entry
                            active_trade['be_moved'] = True
                            
                is_closed = False
                close_price = 0
                pnl = 0
                
                if active_trade['type'] == 'BUY':
                    if active_trade['partial_taken']:
                        # Trailing check
                        df_m15_sub = raw_df.iloc[max(0, raw_idx-50):raw_idx+1]
                        sh_m15, sl_m15 = indicators.find_swings(df_m15_sub, left=4, right=2)
                        if sl_m15:
                            new_sl = sl_m15[-1]['price']
                            if new_sl > active_trade['sl']:
                                active_trade['sl'] = new_sl
                                
                    if current_low <= active_trade['sl']:
                        is_closed = True
                        close_price = active_trade['sl']
                        if active_trade['partial_taken']:
                            pnl = (active_trade['units'] / 2) * (close_price - entry)
                        else:
                            pnl = active_trade['units'] * (close_price - entry)
                    elif current_high >= active_trade['tp']:
                        is_closed = True
                        close_price = active_trade['tp']
                        if active_trade['partial_taken']:
                            pnl = (active_trade['units'] / 2) * (close_price - entry)
                        else:
                            pnl = active_trade['units'] * (close_price - entry)
                else: # SELL
                    if active_trade['partial_taken']:
                        df_m15_sub = raw_df.iloc[max(0, raw_idx-50):raw_idx+1]
                        sh_m15, sl_m15 = indicators.find_swings(df_m15_sub, left=4, right=2)
                        if sh_m15:
                            new_sl = sh_m15[-1]['price']
                            if new_sl < active_trade['sl']:
                                active_trade['sl'] = new_sl
                                
                    if current_high >= active_trade['sl']:
                        is_closed = True
                        close_price = active_trade['sl']
                        if active_trade['partial_taken']:
                            pnl = (active_trade['units'] / 2) * (entry - close_price)
                        else:
                            pnl = active_trade['units'] * (entry - close_price)
                    elif current_low <= active_trade['tp']:
                        is_closed = True
                        close_price = active_trade['tp']
                        if active_trade['partial_taken']:
                            pnl = (active_trade['units'] / 2) * (entry - close_price)
                        else:
                            pnl = active_trade['units'] * (entry - close_price)
                            
                if is_closed:
                    balance += pnl
                    # Track drawdown
                    if balance > peak: peak = balance
                    dd = (peak - balance) / peak * 100.0
                    if dd > max_drawdown: max_drawdown = dd
                    
                    trades.append({
                        'symbol': sym,
                        'type': active_trade['type'],
                        'entry': entry,
                        'sl': active_trade['sl'],
                        'tp': active_trade['tp'],
                        'pnl': pnl,
                        'win': pnl > 0
                    })
                    active_trades[sym] = None
                    
            # 2. Check for new signals for this symbol
            if active_trades[sym] is None:
                df_m15_sub = raw_df.iloc[max(0, raw_idx-200):raw_idx+1]
                h1_time = current_time.replace(minute=0, second=0)
                raw_h1 = h1_data[sym]
                df_h1_sub = raw_h1[raw_h1['time'] <= h1_time]
                if len(df_h1_sub) < 100:
                    continue
                df_h1_sub = df_h1_sub.iloc[-100:]
                
                # Check session
                hour = current_time.hour
                if not (13 <= hour <= 23):
                    continue
                    
                # Mon-Thu filter
                if current_time.weekday() >= 4:
                    continue
                    
                # Swings (using optimal parameters H1(4,2) and M15(4,2) or (2,1))
                # For XAUUSD and GBPUSD, let's use the default (4,2) which is stable and optimized
                sh_h1, sl_h1 = indicators.find_swings(df_h1_sub, left=4, right=2)
                sh_m15, sl_m15 = indicators.find_swings(df_m15_sub, left=4, right=2)
                
                trend = indicators.get_market_trend(df_h1_sub, sh_h1, sl_h1)
                if trend == 'SIDEWAYS':
                    continue
                    
                fibs = indicators.calculate_fibonacci_zones(trend, sh_m15, sl_m15)
                if not fibs:
                    continue
                fib_05 = fibs[0.5]
                fib_0786 = fibs[0.786]
                
                in_fib = False
                if trend == 'UPTREND':
                    in_fib = fib_0786 <= current_close <= fib_05
                else:
                    in_fib = fib_05 <= current_close <= fib_0786
                    
                if not in_fib:
                    continue
                    
                # Confluences (FVG/OB)
                fvgs = indicators.find_fvgs(df_m15_sub, lookback=40)
                obs = indicators.find_order_blocks(df_m15_sub, sh_m15, sl_m15, lookback=100)
                
                in_fvg = False
                for fvg in fvgs:
                    if trend == 'UPTREND' and fvg['type'] == 'BULLISH' and fvg['bottom'] <= current_close <= fvg['top']:
                        in_fvg = True
                    elif trend == 'DOWNTREND' and fvg['type'] == 'BEARISH' and fvg['bottom'] <= current_close <= fvg['top']:
                        in_fvg = True
                        
                in_ob = False
                for ob in obs:
                    if trend == 'UPTREND' and ob['type'] == 'BULLISH' and ob['bottom'] <= current_close <= ob['top']:
                        in_ob = True
                    elif trend == 'DOWNTREND' and ob['type'] == 'BEARISH' and ob['bottom'] <= current_close <= ob['top']:
                        in_ob = True
                        
                if not (in_fvg or in_ob):
                    continue
                    
                # ATR
                df_h1_sub_atr = indicators.calculate_atr(df_h1_sub.copy())
                atr_val = df_h1_sub_atr['atr'].iloc[-1] if 'atr' in df_h1_sub_atr.columns else (current_close * 0.001)
                atr_buffer = atr_val * 0.5
                
                # SL H1 Swing
                if trend == 'UPTREND':
                    base_sl = sl_h1[-1]['price'] if sl_h1 else df_h1_sub['low'].iloc[-20:].min()
                    sl = base_sl - atr_buffer
                    if sl >= current_close:
                        sl = df_m15_sub['low'].iloc[-15:].min() - (current_close * 0.0005)
                    tp = strategy.find_h1_tp_target(trend, current_close, sh_h1, sl_h1)
                else:
                    base_sl = sh_h1[-1]['price'] if sh_h1 else df_h1_sub['high'].iloc[-20:].max()
                    sl = base_sl + atr_buffer
                    if sl <= current_close:
                        sl = df_m15_sub['high'].iloc[-15:].max() + (current_close * 0.0005)
                    tp = strategy.find_h1_tp_target(trend, current_close, sh_h1, sl_h1)
                    
                risk_dist = abs(current_close - sl)
                reward_dist = abs(tp - current_close)
                
                if risk_dist <= 0:
                    continue
                    
                rr = reward_dist / risk_dist
                if rr < 1.5:
                    continue
                    
                risk_usd = balance * risk_pct
                units = risk_usd / risk_dist
                
                active_trades[sym] = {
                    'type': 'BUY' if trend == 'UPTREND' else 'SELL',
                    'entry': current_close,
                    'sl': sl,
                    'tp': tp,
                    'risk_distance': risk_dist,
                    'units': units,
                    'be_moved': False,
                    'partial_taken': False
                }
                
        # Final Stats
        net_profit = balance - initial_balance
        pct_profit = (net_profit / initial_balance) * 100.0
        win_trades = [t for t in trades if t['win']]
        win_rate = len(win_trades) / len(trades) if len(trades) > 0 else 0
        
        results[risk_pct] = {
            'trades': len(trades),
            'profit_pct': pct_profit,
            'win_rate': win_rate,
            'max_drawdown': max_drawdown
        }
        
    print("\n=============================================")
    print(" KET QUA KHAO SAT HE SO DRAWDOWN THEO RUI RO ")
    print("=============================================")
    print(f"{'Muc Rui Ro':<12} | {'Tong Lenh':<9} | {'Ti Le Thang':<11} | {'Loi Nhuan %':<12} | {'Max Drawdown %'}")
    print("-" * 65)
    for r, v in results.items():
        print(f"{r*100:9.1f}% | {v['trades']:9} | {v['win_rate']*100:10.1f}% | {v['profit_pct']:+11.2f}% | {v['max_drawdown']:13.2f}%")
    print("=============================================")

if __name__ == '__main__':
    run_drawdown_backtest()
