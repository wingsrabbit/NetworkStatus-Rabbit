import json, sys
d = json.load(sys.stdin)
data = d.get("data", [])
print(f"count={len(data)}")
if data:
    print(f"first: {data[0]}")
    print(f"last: {data[-1]}")
else:
    print("empty")
