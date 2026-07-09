from flask import Blueprint, jsonify

from services.docker_service import create_canary

deploy_bp = Blueprint("deploy", __name__)

@deploy_bp.route("/deploy", methods=["POST"])
def deploy():

    result = create_canary()

    return jsonify(result)