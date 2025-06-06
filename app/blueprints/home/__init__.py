from flask import Blueprint, render_template
from app.middleware.auth import auth_required

home_bp = Blueprint("home", __name__)


@home_bp.route("/")
@auth_required
def index():
    return render_template("home/index.html")
