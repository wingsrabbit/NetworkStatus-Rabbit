from server.api.auth import auth_bp
from server.api.nodes import nodes_bp
from server.api.tasks import tasks_bp
from server.api.data import data_bp
from server.api.users import users_bp
from server.api.alerts import alerts_bp
from server.api.settings import settings_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(nodes_bp, url_prefix='/api/nodes')
    app.register_blueprint(tasks_bp, url_prefix='/api/tasks')
    app.register_blueprint(data_bp, url_prefix='/api/data')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(alerts_bp, url_prefix='/api/alerts')
    app.register_blueprint(settings_bp, url_prefix='/api/settings')

    # Serve install-agent.sh script
    import os
    from flask import send_file

    @app.route('/api/install-agent.sh')
    def serve_install_script():
        script_path = os.path.join(app.root_path, '..', 'scripts', 'install-agent.sh')
        return send_file(script_path, mimetype='text/x-shellscript')

    @app.route('/api/agent-package.tar.gz')
    def serve_agent_package():
        """Package and serve agent code as tarball for one-click install."""
        import tarfile
        import io
        agent_dir = os.path.join(app.root_path, '..', 'agent')
        req_file = os.path.join(app.root_path, '..', 'requirements-agent.txt')
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w:gz') as tar:
            tar.add(agent_dir, arcname='agent')
            if os.path.exists(req_file):
                tar.add(req_file, arcname='requirements-agent.txt')
        buf.seek(0)
        return send_file(buf, mimetype='application/gzip',
                         download_name='agent-package.tar.gz', as_attachment=True)
