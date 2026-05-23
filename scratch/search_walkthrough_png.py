with open(r"C:\Users\Duc\.gemini\antigravity\brain\641e3479-d98a-4ba2-a577-bc54bb3a849b\walkthrough.md", "r", encoding="utf-8") as f:
    content = f.read()

import re
matches = re.findall(r'!\[.*?\]\(.*?\)', content)
print("Found image tags:")
for m in matches:
    print(m)
