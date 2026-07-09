from flask import Blueprint, jsonify

from services.docker_service import promote_canary

promote_bp = Blueprint("promote", __name__)


@promote_bp.route("/promote", methods=["POST"])
def promote():

    result = promote_canary()

    return jsonify(result)