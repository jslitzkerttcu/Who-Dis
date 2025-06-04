from flask import Blueprint, render_template, request, jsonify
from app.middleware.auth import require_role
from app.services.ldap_service import ldap_service
from app.services.genesys_service import genesys_service
import logging

logger = logging.getLogger(__name__)

search_bp = Blueprint('search', __name__)


@search_bp.route('/')
@require_role('viewer')
def index():
    return render_template('search/index.html')


@search_bp.route('/user', methods=['POST'])
@require_role('viewer')
def search_user():
    data = request.get_json()
    search_term = data.get('search_term', '').strip()
    
    if not search_term:
        return jsonify({'error': 'Search term is required'}), 400
    
    logger.info(f"Searching for user: {search_term}")
    
    ldap_result = None
    genesys_result = None
    
    try:
        ldap_result = ldap_service.search_user(search_term)
    except Exception as e:
        logger.error(f"LDAP search error: {str(e)}")
    
    try:
        genesys_result = genesys_service.search_user(search_term)
    except Exception as e:
        logger.error(f"Genesys search error: {str(e)}")
    
    return jsonify({
        'ldap': ldap_result,
        'genesys': genesys_result,
        'search_term': search_term
    })