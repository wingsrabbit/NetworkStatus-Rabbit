from server.ws.agent_handler import register_agent_handlers
from server.ws.dashboard_handler import register_dashboard_handlers


def register_ws_handlers(socketio):
    register_agent_handlers(socketio)
    register_dashboard_handlers(socketio)
