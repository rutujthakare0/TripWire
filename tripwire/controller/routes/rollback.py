from flask import Blueprint, jsonify

from services.docker_service import rollback_canary

rollback_bp = Blueprint("rollback", __name__)


@rollback_bp.route("/rollback", methods=["POST"])
def rollback():

    result = rollback_canary()

    return jsonify(result)