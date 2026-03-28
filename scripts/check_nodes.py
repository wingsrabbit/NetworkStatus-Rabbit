from server.database import get_db_session
from server.models import Node, Task

with get_db_session() as s:
    print("=== NODES ===")
    for n in s.query(Node).all():
        print(f"{n.name}: config_version={n.config_version}, synced={n.synced_config_version}, status={n.status}")
    
    print("\n=== TASKS (by source node) ===")
    for t in s.query(Task).order_by(Task.source_node_id, Task.name).all():
        print(f"  {t.name}: source={t.source_node_id}, target={t.target}, proto={t.protocol}, enabled={t.enabled}")
