from flask import Flask, g
import os
import logging


def create_app():
    app = Flask(__name__)
    
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    @app.before_request
    def before_request():
        g.user = None
        g.role = None
    
    @app.context_processor
    def inject_user():
        return dict(g=g)
    
    from app.blueprints.home import home_bp
    from app.blueprints.search import search_bp
    from app.blueprints.admin import admin_bp
    
    app.register_blueprint(home_bp)
    app.register_blueprint(search_bp, url_prefix='/search')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    return app