from flask import Blueprint, jsonify, request
from services.docker_service import create_canary

deploy_bp = Blueprint("deploy", __name__)


@deploy_bp.route("/deploy", methods=["POST"])
def deploy():
    data = request.get_json(silent=True) or {}
    image      = data.get("image", None)       # specific image from CI
    chaos_mode = data.get("chaos_mode", "none")

    result = create_canary(image=image, chaos_mode=chaos_mode)
    return jsonify(result)