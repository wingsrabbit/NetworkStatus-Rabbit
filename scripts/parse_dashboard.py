import json, sys

d = json.load(sys.stdin)
print(f"nodes: {len(d.get('nodes', []))}")
print(f"tasks: {len(d.get('tasks', []))}")
for t in d.get('tasks', [])[:20]:
    lr = t.get('latest') or t.get('latest_result')
    status = lr.get('success', '?') if lr else 'no data'
    latency = lr.get('latency', '-') if lr else '-'
    print(f"  {t.get('name', t.get('task_id','?'))}: success={status}, latency={latency}")
