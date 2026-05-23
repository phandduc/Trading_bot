import MetaTrader5 as mt5

if mt5.initialize():
    print("MT5 methods starting with 'chart':")
    for x in dir(mt5):
        if 'chart' in x.lower():
            print(f"- {x}")
    mt5.shutdown()
else:
    print("MT5 init failed")
