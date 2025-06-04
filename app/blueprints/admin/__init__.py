from flask import Blueprint, render_template
from app.middleware.auth import require_role

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/')
@require_role('admin')
def index():
    return render_template('admin/index.html')