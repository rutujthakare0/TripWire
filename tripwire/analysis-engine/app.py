from threading import Thread

from flask import Flask

from services.analyzer import monitor

app = Flask(__name__)


@app.route("/health")
def health():

    return {
        "status": "ok"
    }


Thread(target=monitor, daemon=True).start()


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=7000
    )