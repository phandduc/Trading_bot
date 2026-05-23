import os
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
import numpy as np

def plot_trade_chart(symbol, df_m15, entry_price, sl, tp, fvgs=None, obs=None, save_path=None):
    """
    Vẽ biểu đồ hình nến M15 đẹp mắt (Dark Mode) cho thấy điểm Entry, SL, TP, và các vùng hợp lưu FVG/OB.
    """
    if df_m15 is None or len(df_m15) == 0:
        print("Cannot plot chart: Empty dataframe")
        return False

    # Chỉ vẽ 80 nến gần nhất để biểu đồ nhìn rõ ràng và không bị rối
    df = df_m15.iloc[-80:].copy().reset_index(drop=True)
    
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # 1. Vẽ các cây nến (Candlestick chart)
    for i in range(len(df)):
        open_p = df.loc[i, 'open']
        close_p = df.loc[i, 'close']
        high_p = df.loc[i, 'high']
        low_p = df.loc[i, 'low']
        
        # Xác định màu nến
        color = '#00e676' if close_p >= open_p else '#ff1744'  # Xanh lá / Đỏ neon
        
        # Vẽ râu nến (wicks)
        ax.plot([i, i], [low_p, high_p], color=color, linewidth=1.5)
        
        # Vẽ thân nến (body)
        rect = patches.Rectangle((i - 0.35, min(open_p, close_p)), 0.7, abs(close_p - open_p),
                                 facecolor=color, edgecolor=color, alpha=0.9, linewidth=0)
        ax.add_patch(rect)
        
    # 2. Vẽ các vùng FVG (Fair Value Gaps) nếu có
    # Chúng tôi định vị FVG trên trục X dựa trên thời gian thực
    if fvgs:
        for fvg in fvgs:
            # Tìm xem FVG nằm ở đâu trong 80 nến hiển thị
            fvg_time = fvg.get('time')
            fvg_indices = df[df['time'] == fvg_time].index
            if len(fvg_indices) > 0:
                idx = fvg_indices[0]
                # Vẽ hình chữ nhật từ cây nến FVG kéo dài đến cuối biểu đồ bên phải
                color = '#00b0ff'  # Xanh dương neon
                rect = patches.Rectangle((idx, fvg['bottom']), len(df) - idx, fvg['top'] - fvg['bottom'],
                                         facecolor=color, alpha=0.15, edgecolor=color, linestyle='--', linewidth=0.5)
                ax.add_patch(rect)
                
    # 3. Vẽ các vùng Order Block (OB) nếu có
    if obs:
        for ob in obs:
            ob_time = ob.get('time')
            ob_indices = df[df['time'] == ob_time].index
            if len(ob_indices) > 0:
                idx = ob_indices[0]
                color = '#ff9100'  # Cam neon
                rect = patches.Rectangle((idx, ob['bottom']), len(df) - idx, ob['top'] - ob['bottom'],
                                         facecolor=color, alpha=0.15, edgecolor=color, linestyle=':', linewidth=0.5)
                ax.add_patch(rect)
                
    # 4. Vẽ các đường ngang đại diện cho điểm Entry, SL và TP
    # Entry line
    ax.axhline(y=entry_price, color='#2979ff', linestyle='--', linewidth=1.8, label=f'Entry: {entry_price:.5f}')
    ax.text(0, entry_price, f'  Entry: {entry_price:.5f}', color='#2979ff', va='bottom', ha='left', fontweight='bold', fontsize=10)
    
    # Stop Loss line (Đỏ)
    ax.axhline(y=sl, color='#f44336', linestyle='-', linewidth=2.0, label=f'SL: {sl:.5f}')
    ax.text(0, sl, f'  Stop Loss: {sl:.5f}', color='#f44336', va='bottom', ha='left', fontweight='bold', fontsize=10)
    
    # Take Profit line (Xanh lá)
    ax.axhline(y=tp, color='#4caf50', linestyle='-', linewidth=2.0, label=f'TP: {tp:.5f}')
    ax.text(0, tp, f'  Take Profit: {tp:.5f}', color='#4caf50', va='bottom', ha='left', fontweight='bold', fontsize=10)
    
    # 5. Định dạng trục và hiển thị
    ax.set_title(f"BIỂU ĐỒ PHÂN TÍCH GIAO DỊCH {symbol.upper()} (M15)", color='white', fontsize=14, fontweight='bold', pad=15)
    
    # Hiển thị nhãn thời gian cho các nến (cứ mỗi 10 nến chọn 1 nhãn)
    step = max(1, len(df) // 8)
    xticks_indices = list(range(0, len(df), step))
    # Định dạng nhãn thời gian từ Timestamp
    xticks_labels = []
    for idx in xticks_indices:
        t = df.loc[idx, 'time']
        if isinstance(t, str):
            xticks_labels.append(t[11:16]) # Lấy giờ:phút
        elif hasattr(t, 'strftime'):
            xticks_labels.append(t.strftime('%H:%M'))
        else:
            # Giả định timestamp số nguyên
            try:
                dt = pd.to_datetime(t, unit='s')
                xticks_labels.append(dt.strftime('%H:%M'))
            except:
                xticks_labels.append("")
                
    ax.set_xticks(xticks_indices)
    ax.set_xticklabels(xticks_labels, color='#b0bec5', fontsize=9)
    ax.tick_params(axis='y', colors='#b0bec5', labelsize=10)
    
    # Grid nhẹ ẩn dưới biểu đồ
    ax.grid(color='#37474f', linestyle=':', linewidth=0.5, alpha=0.5)
    
    # Khung viền biểu đồ
    for spine in ax.spines.values():
        spine.set_color('#37474f')
        spine.set_linewidth(1.0)
        
    plt.tight_layout()
    
    # 6. Lưu file hình ảnh
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=120, bbox_inches='tight', facecolor='#121212')
        print(f"Chart saved successfully at: {save_path}")
        plt.close()
        return True
    else:
        plt.close()
        return False
