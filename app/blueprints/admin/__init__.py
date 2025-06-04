from flask import Blueprint, render_template, jsonify
from app.middleware.auth import require_role
from app.services.genesys_cache import genesys_cache

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/')
@require_role('admin')
def index():
    return render_template('admin/index.html')


@admin_bp.route('/cache-status')
@require_role('admin')
def cache_status():
    """Get Genesys cache status."""
    return jsonify(genesys_cache.get_cache_status())