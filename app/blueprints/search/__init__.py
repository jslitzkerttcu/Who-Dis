from flask import Blueprint, render_template, request
from app.middleware.auth import require_role

search_bp = Blueprint('search', __name__)


@search_bp.route('/')
@require_role('viewer')
def index():
    query = request.args.get('q', '')
    return render_template('search/index.html', query=query)