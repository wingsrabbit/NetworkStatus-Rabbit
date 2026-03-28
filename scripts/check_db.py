import sys
sys.path.insert(0, '/app')
from server.app import create_app
app = create_app()
with app.app_context():
    from server.extensions import db
    from server.models import Node, ProbeTask
    for n in Node.query.all():
        print(f"NODE {n.name}: config_version={n.config_version}, status={n.status}, id={n.id}")
    print()
    for t in ProbeTask.query.order_by(ProbeTask.source_node_id, ProbeTask.name).all():
        print(f"  TASK {t.name}: source={t.source_node_id}, target={t.target}, proto={t.protocol}, enabled={t.enabled}")
