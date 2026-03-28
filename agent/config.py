"""Agent configuration."""
import argparse
import os


class AgentConfig:
    def __init__(self):
        self.server = 'localhost'
        self.port = 9192
        self.node_id = ''
        self.token = ''
        self.data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'agent_data')
        self.listen_port = None  # None = disabled (NAT-safe default)
        self.listen_ready = False  # True if echo servers bound successfully

    @classmethod
    def from_args(cls):
        parser = argparse.ArgumentParser(description='NetworkStatus-Rabbit Agent')
        parser.add_argument('--server', required=True, help='Center server address')
        parser.add_argument('--port', type=int, default=9192, help='Center server port (agent channel)')
        parser.add_argument('--node-id', required=True, help='Node ID')
        parser.add_argument('--token', required=True, help='Authentication token')
        parser.add_argument('--data-dir', default=None, help='Data directory for local cache')
        parser.add_argument('--listen-port', type=int, default=None,
                            help='Optional echo port (TCP+UDP). Enables this agent as an internal probe target.')

        args = parser.parse_args()
        config = cls()
        config.server = args.server
        config.port = args.port
        config.node_id = args.node_id
        config.token = args.token
        config.listen_port = args.listen_port
        if args.data_dir:
            config.data_dir = args.data_dir

        os.makedirs(config.data_dir, exist_ok=True)
        return config

    @property
    def server_url(self):
        return f'http://{self.server}:{self.port}'

    @property
    def db_path(self):
        return os.path.join(self.data_dir, 'agent_cache.db')
