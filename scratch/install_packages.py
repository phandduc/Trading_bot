import subprocess
import sys

print("Checking packages...")
try:
    import matplotlib
    import matplotlib.pyplot as plt
    print("matplotlib is already installed.")
except ImportError:
    print("matplotlib not found. Installing...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "matplotlib"])
        print("matplotlib installed successfully.")
    except Exception as e:
        print(f"Failed to install matplotlib: {e}")
