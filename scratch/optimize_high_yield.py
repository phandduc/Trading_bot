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

def run_optimization():
    print("=== BAT DAU TOI UU HOA SAN PHAN TRONG 180 NGAY ===")
    if not data_provider.initialize_mt5():
        print("MetaTrader5 initialize failed")
        return
        
    symbol = "XAUUSD"
    actual_sym = data_provider.get_actual_symbol(symbol)
    
    # Get bars
    print(f"Loading data for {actual_sym}...")
    df_m15 = data_provider.get_rates(actual_sym, 'M15', 180 * 96)
    df_h1 = data_provider.get_rates(actual_sym, 'H1', 180 * 24)
    
    mt5.shutdown()
    
    if df_m15 is None or df_h1 is None:
        print("Failed to download rates")
        return
        
    print(f"Downloaded {len(df_h1)} H1 bars and {len(df_m15)} M15 bars.")
    
    results = []
    
    # Define the simulation function
    def simulate_backtest(df_h1_raw, df_m15_raw, left_h1, right_h1, left_m15, right_m15, risk_pct, sl_mode, be_ratio, weekday_filter):
        initial_balance = 10000.0
        balance = initial_balance
        active_trade = None
        trades = []
        
        # Loop through each M15 bar starting from index 500
        for i in range(500, len(df_m15_raw)):
            current_bar = df_m15_raw.iloc[i]
            current_time = current_bar['time']
            current_close = current_bar['close']
            current_high = current_bar['high']
            current_low = current_bar['low']
            
            # Check active trade
            if active_trade is not None:
                risk_dist = active_trade['risk_distance']
                entry = active_trade['entry']
                
                # Check BE
                if not active_trade['be_moved']:
                    if active_trade['type'] == 'BUY':
                        if current_high >= entry + (risk_dist * be_ratio):
                            active_trade['sl'] = entry
                            active_trade['be_moved'] = True
                    else:
                        if current_low <= entry - (risk_dist * be_ratio):
                            active_trade['sl'] = entry
                            active_trade['be_moved'] = True
                            
                # Check Partial TP (PARTIAL_1.5)
                if not active_trade['partial_taken']:
                    partial_tp_dist = risk_dist * 1.5
                    if active_trade['type'] == 'BUY':
                        if current_high >= entry + partial_tp_dist:
                            realized_pnl = (active_trade['units'] / 2) * ( (entry + partial_tp_dist) - entry )
                            balance += realized_pnl
                            active_trade['partial_taken'] = True
                            active_trade['sl'] = entry
                            active_trade['be_moved'] = True
                    else:
                        if current_low <= entry - partial_tp_dist:
                            realized_pnl = (active_trade['units'] / 2) * ( entry - (entry - partial_tp_dist) )
                            balance += realized_pnl
                            active_trade['partial_taken'] = True
                            active_trade['sl'] = entry
                            active_trade['be_moved'] = True
                            
                is_closed = False
                close_price = 0
                pnl = 0
                
                if active_trade['type'] == 'BUY':
                    if active_trade['partial_taken']:
                        # Simple structural trailing check (optimized lookup to run faster)
                        df_m15_sub = df_m15_raw.iloc[max(0, i-50):i+1]
                        sh_m15, sl_m15 = indicators.find_swings(df_m15_sub, left=left_m15, right=right_m15)
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
                        df_m15_sub = df_m15_raw.iloc[max(0, i-50):i+1]
                        sh_m15, sl_m15 = indicators.find_swings(df_m15_sub, left=left_m15, right=right_m15)
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
                    trades.append({
                        'type': active_trade['type'],
                        'entry': entry,
                        'sl': active_trade['sl'],
                        'tp': active_trade['tp'],
                        'pnl': pnl,
                        'win': pnl > 0
                    })
                    active_trade = None
                    
            # Check for new signals
            if active_trade is None:
                df_m15_sub = df_m15_raw.iloc[max(0, i-200):i+1]
                h1_time = current_time.replace(minute=0, second=0)
                df_h1_sub = df_h1_raw[df_h1_raw['time'] <= h1_time]
                if len(df_h1_sub) < 100:
                    continue
                df_h1_sub = df_h1_sub.iloc[-100:]
                
                # Check session
                hour = current_time.hour
                if not (13 <= hour <= 23):
                    continue
                    
                if weekday_filter and current_time.weekday() >= 4:
                    continue
                    
                # Swings
                sh_h1, sl_h1 = indicators.find_swings(df_h1_sub, left=left_h1, right=right_h1)
                sh_m15, sl_m15 = indicators.find_swings(df_m15_sub, left=left_m15, right=right_m15)
                
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
                    
                # Confluences
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
                
                if sl_mode == 'H1':
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
                else: # M15 swing (much tighter!)
                    if trend == 'UPTREND':
                        base_sl = sl_m15[-1]['price'] if sl_m15 else df_m15_sub['low'].iloc[-15:].min()
                        sl = base_sl - (atr_buffer * 0.3)
                        if sl >= current_close:
                            sl = df_m15_sub['low'].iloc[-5:].min() - (current_close * 0.0002)
                        tp = strategy.find_h1_tp_target(trend, current_close, sh_h1, sl_h1)
                    else:
                        base_sl = sh_m15[-1]['price'] if sh_m15 else df_m15_sub['high'].iloc[-15:].max()
                        sl = base_sl + (atr_buffer * 0.3)
                        if sl <= current_close:
                            sl = df_m15_sub['high'].iloc[-5:].max() + (current_close * 0.0002)
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
                
                active_trade = {
                    'type': 'BUY' if trend == 'UPTREND' else 'SELL',
                    'entry': current_close,
                    'sl': sl,
                    'tp': tp,
                    'risk_distance': risk_dist,
                    'units': units,
                    'be_moved': False,
                    'partial_taken': False
                }
                
        net_profit = balance - initial_balance
        pct_profit = (net_profit / initial_balance) * 100.0
        win_trades = [t for t in trades if t['win']]
        win_rate = len(win_trades) / len(trades) if len(trades) > 0 else 0
        
        return len(trades), pct_profit, win_rate
        
    print("Testing combinations...")
    # Loop over combinations
    for left_h1, right_h1 in [(4, 2), (2, 1)]:
        for left_m15, right_m15 in [(4, 2), (2, 1)]:
            for risk_pct in [0.01, 0.02, 0.03, 0.05]:
                for sl_mode in ['H1', 'M15']:
                    for be_ratio in [0.8]:
                        for weekday_filter in [True, False]:
                            total_trades, pct_profit, win_rate = simulate_backtest(
                                df_h1, df_m15, left_h1, right_h1, left_m15, right_m15,
                                risk_pct, sl_mode, be_ratio, weekday_filter
                            )
                            # Print combination result
                            print(f"H1({left_h1},{right_h1}) | M15({left_m15},{right_m15}) | Risk:{risk_pct*100}% | SL:{sl_mode} | BE:{be_ratio} | WDay:{weekday_filter} -> Trades:{total_trades} | Profit:{pct_profit:.2f}% | WR:{win_rate*100:.1f}%")
                            
                            results.append({
                                'left_h1': left_h1, 'right_h1': right_h1,
                                'left_m15': left_m15, 'right_m15': right_m15,
                                'risk_pct': risk_pct, 'sl_mode': sl_mode,
                                'be_ratio': be_ratio, 'weekday_filter': weekday_filter,
                                'total_trades': total_trades, 'pct_profit': pct_profit,
                                'win_rate': win_rate
                            })
                                
    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values(by='pct_profit', ascending=False)
        results_df.to_csv('high_yield_optimization_results.csv', index=False)
        print("\n=== TOP 10 OPTIMIZATION COMBINATIONS ===")
        print(results_df.head(10).to_string())
    else:
        print("No combinations evaluated.")

if __name__ == '__main__':
    run_optimization()
