import sys
sys.path.insert(0, '/app')
from server.app import create_app
app = create_app()
with app.app_context():
    from server.extensions import db
    from server.models import Node, ProbeTask

    print("=== NODES ===")
    for n in Node.query.all():
        task_count = ProbeTask.query.filter_by(source_node_id=n.id, enabled=True).count()
        print(f"  {n.name}: cv={n.config_version}, status={n.status}, tasks={task_count}")

    print("\n=== TASKS ===")
    for t in ProbeTask.query.order_by(ProbeTask.source_node_id, ProbeTask.name).all():
        src = Node.query.get(t.source_node_id)
        addr = t.target_address or (t.target_node.name if t.target_node else '?')
        print(f"  {t.name}: src={src.name if src else '?'}, target={addr}, proto={t.protocol}, port={t.target_port}, enabled={t.enabled}")

    # Fix config versions for A2 and A3 to 5
    print("\n=== FIXING CONFIG VERSIONS ===")
    for n in Node.query.all():
        if n.config_version < 5:
            old = n.config_version
            n.config_version = 5
            db.session.commit()
            print(f"  {n.name}: {old} -> 5")
        else:
            print(f"  {n.name}: already at {n.config_version}")
