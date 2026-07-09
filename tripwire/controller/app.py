from flask import Flask

from routes.deploy import deploy_bp
from routes.promote import promote_bp
from routes.rollback import rollback_bp

app = Flask(__name__)

app.register_blueprint(deploy_bp)
app.register_blueprint(promote_bp)
app.register_blueprint(rollback_bp)


@app.route("/health")
def health():
    return {
        "status": "ok",
        "service": "controller"
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)