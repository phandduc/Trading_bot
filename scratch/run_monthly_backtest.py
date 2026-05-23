import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys

# Add project root to path
sys.path.append(r"C:\Users\Duc\.gemini\antigravity\scratch\xauusd_trading_bot")

import data_provider
import strategy
import config
import indicators
import backtest

def calculate_monthly_metrics(trades, start_balance=10000.0, risk_percent=2.0):
    trades = sorted([t for t in trades if t['exit_time'] is not None], key=lambda x: x['exit_time'])
    
    balance = start_balance
    peak = start_balance
    
    equity_curve = []
    pnl_multiplier = risk_percent
    
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
    if df_equity.empty:
        return None
        
    df_equity['month'] = df_equity['exit_time'].apply(lambda x: x.strftime('%Y-%m'))
    months = sorted(df_equity['month'].unique())
    
    monthly_data = []
    prev_month_balance = start_balance
    
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
        
        m_start_balance = prev_month_balance
        m_end_balance = m_trades.iloc[-1]['balance']
        profit_pct = ((m_end_balance - m_start_balance) / m_start_balance) * 100
        cum_profit_pct = ((m_end_balance - start_balance) / start_balance) * 100
        
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
        
    return {
        'monthly_data': monthly_data,
        'overall_total': overall_total,
        'overall_win_rate': overall_win_rate,
        'overall_tps': len(overall_tps) + len(overall_partial_wins),
        'overall_sls': len(overall_sls),
        'overall_bes': len(overall_bes) - len(overall_partial_wins),
        'overall_return': overall_return,
        'overall_max_dd': overall_max_dd
    }

def run():
    if not data_provider.initialize_mt5():
        print("Lỗi kết nối MT5")
        return
        
    days = 180
    symbols = ['XAUUSD', 'GBPUSD']
    all_trades = []
    
    for sym in symbols:
        actual_sym = data_provider.get_actual_symbol(sym)
        m15_count = int(days * 96) + 300
        h1_count = int(days * 24) + 300
        df_h1 = data_provider.get_rates(actual_sym, 'H1', h1_count)
        df_m15 = data_provider.get_rates(actual_sym, 'M15', m15_count)
        
        if df_h1 is None or df_m15 is None:
            continue
            
        trades = backtest.run_simulation(df_m15, df_h1, sym, tp_mode='PARTIAL_1.5')
        all_trades.extend(trades)
        
    data_provider.shutdown_mt5()
    
    for r in [1.0, 2.0, 3.0]:
        print(f"\n================ HIỆU SUẤT VỚI RỦI RO {r}% / LỆNH ================")
        res = calculate_monthly_metrics(all_trades, start_balance=10000.0, risk_percent=r)
        if not res:
            continue
            
        m_data = res['monthly_data']
        header = f" {'Tháng':<10} | {'Số lệnh':<8} | {'Winrate':<8} | {'TP/SL/BE':<10} | {'LN Tháng':<12} | {'LN Lũy Kế':<12} | {'DD Max':<10}"
        print(header)
        print("-" * len(header))
        
        for row in m_data:
            print(f" {row['month']:<10} | {row['total']:<8} | {row['win_rate']:7.1f}% | {row['tp_sl_be']:<10} | {row['return_pct']:+11.2f}% | {row['cum_return_pct']:+11.2f}% | {row['max_dd_pct']:9.2f}%")
            
        print("-" * len(header))
        overall_tp_sl_be_str = f"{res['overall_tps']}/{res['overall_sls']}/{res['overall_bes']}"
        print(f" {'Cả kỳ':<10} | {res['overall_total']:<8} | {res['overall_win_rate']:7.1f}% | {overall_tp_sl_be_str:<10} | {res['overall_return']:+11.2f}% | {res['overall_return']:+11.2f}% | {res['overall_max_dd']:9.2f}%")
        print("=" * len(header))

if __name__ == "__main__":
    run()
