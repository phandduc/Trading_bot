with open(r"C:\Users\Duc\.gemini\antigravity\brain\641e3479-d98a-4ba2-a577-bc54bb3a849b\walkthrough.md", "r", encoding="utf-8") as f:
    lines = f.readlines()
for idx, line in enumerate(lines):
    if "media" in line:
        print(f"Line {idx+1}: {line.strip()}")
