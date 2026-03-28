#!/usr/bin/env python3
"""Delete all old tasks and create new ones with unified naming."""
import sys; sys.path.insert(0, '/app')
from server.app import create_app
app = create_app()

A1 = 'b2d8b27d-7400-49fd-972e-298f5bfc3919'  # client-1, .11
A2 = 'e89041c9-f63b-4da3-9152-f31ad707ed10'  # client-2, .12
A3 = 'b06448de-12f4-4412-9121-0b72737d3511'  # client-3, .13
EXT = '45.192.177.60'

agents = {'A1': A1, 'A2': A2, 'A3': A3}

with app.app_context():
    from server.extensions import db
    from server.models.task import ProbeTask

    # Delete ALL existing tasks
    old = ProbeTask.query.all()
    print(f'Deleting {len(old)} old tasks...')
    for t in old:
        db.session.delete(t)
    db.session.commit()
    print('All old tasks deleted.')

    created = 0

    # Internal tasks: ICMP, TCP, UDP between all agent pairs
    for proto in ['icmp', 'tcp', 'udp']:
        for src_name, src_id in agents.items():
            for tgt_name, tgt_id in agents.items():
                if src_name == tgt_name:
                    continue
                name = f'int-{src_name}to{tgt_name}-{proto}'
                task = ProbeTask(
                    name=name,
                    source_node_id=src_id,
                    target_type='internal',
                    target_node_id=tgt_id,
                    protocol=proto,
                    interval=5,
                    timeout=10,
                    enabled=True,
                )
                db.session.add(task)
                created += 1

    # External tasks to 45.192.177.60
    for src_name, src_id in agents.items():
        # ICMP
        task = ProbeTask(
            name=f'glo-{src_name}toEXT-icmp',
            source_node_id=src_id,
            target_type='external',
            target_address=EXT,
            protocol='icmp',
            interval=5,
            timeout=10,
            enabled=True,
        )
        db.session.add(task)
        created += 1

        # TCP to port 80
        task = ProbeTask(
            name=f'glo-{src_name}toEXT-tcp',
            source_node_id=src_id,
            target_type='external',
            target_address=EXT,
            target_port=80,
            protocol='tcp',
            interval=5,
            timeout=10,
            enabled=True,
        )
        db.session.add(task)
        created += 1

        # UDP to port 9200
        task = ProbeTask(
            name=f'glo-{src_name}toEXT-udp',
            source_node_id=src_id,
            target_type='external',
            target_address=EXT,
            target_port=9200,
            protocol='udp',
            interval=5,
            timeout=10,
            enabled=True,
        )
        db.session.add(task)
        created += 1

        # HTTP (HTTPS) to 45.192.177.60
        task = ProbeTask(
            name=f'glo-{src_name}toEXT-http',
            source_node_id=src_id,
            target_type='external',
            target_address=f'https://{EXT}',
            protocol='http',
            interval=5,
            timeout=10,
            enabled=True,
        )
        db.session.add(task)
        created += 1

        # DNS - resolve wingsrabbit.com
        task = ProbeTask(
            name=f'glo-{src_name}toEXT-dns',
            source_node_id=src_id,
            target_type='external',
            target_address='wingsrabbit.com',
            protocol='dns',
            interval=5,
            timeout=10,
            enabled=True,
        )
        db.session.add(task)
        created += 1

    db.session.commit()
    print(f'Created {created} new tasks.')

    # Bump config version to trigger re-sync
    from server.models.node import Node
    for n in Node.query.all():
        n.config_version = (n.config_version or 0) + 1
    db.session.commit()
    print('Config versions bumped. Agents will re-sync.')

    # List all tasks
    print('\n=== NEW TASKS ===')
    for t in ProbeTask.query.order_by(ProbeTask.name).all():
        print(f'  {t.name} | {t.protocol} | src={t.source_node_id[:8]} | type={t.target_type} | target={t.target_address or t.target_node_id} | port={t.target_port}')
