from flask import Blueprint

utilities = Blueprint("utilities", __name__, url_prefix="/utilities")

from . import blocked_numbers as blocked_numbers  # noqa: E402
