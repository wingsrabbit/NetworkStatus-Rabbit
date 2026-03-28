#!/usr/bin/env python3
import sys; sys.path.insert(0, '/app')
from server.app import create_app
app = create_app()
with app.app_context():
    from server.models.task import ProbeTask
    from server.models.node import Node
    print('=== NODES ===')
    for n in Node.query.all():
        print(f'{n.id}|{n.name}|{n.status}|{n.public_ip}')
    print()
    print('=== TASKS ===')
    for t in ProbeTask.query.all():
        print(f'{t.id}|{t.name}|{t.protocol}|{t.source_node_id}|{t.target_type}|{t.target_address}|{t.target_port}|{t.target_node_id}')
