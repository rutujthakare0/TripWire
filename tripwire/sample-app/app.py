import os
import time
import random
from flask import Flask, jsonify
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# ---------------- Metrics ----------------
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status','version']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'Request latency',
    ['endpoint','version'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5]
)

# ---------------- Config ----------------
VERSION = os.getenv("APP_VERSION", "v1")
CHAOS_MODE = os.getenv("CHAOS_MODE", "none")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "version": VERSION
    })


@app.route("/process")
def process():
    start = time.time()

    # ---- chaos injection ----
    if CHAOS_MODE == "latency":
        time.sleep(random.uniform(0.8, 2.5))

    elif CHAOS_MODE == "error":
        if random.random() < 0.4:
            duration = time.time() - start
            REQUEST_LATENCY.labels(endpoint="/process",version=VERSION).observe(duration)
            REQUEST_COUNT.labels(method="GET",endpoint="/process",status="500",version=VERSION).inc()
            return jsonify({"error": "failure"}), 500

    # ---- normal execution ----
    time.sleep(random.uniform(0.01, 0.05))

    duration = time.time() - start

    REQUEST_LATENCY.labels(endpoint="/process",version=os.getenv("APP_VERSION")).observe(duration)
    REQUEST_COUNT.labels(method="GET", endpoint="/process", status="200",version=os.getenv("APP_VERSION")).inc()

    return jsonify({
        "result": "processed",
        "version": VERSION
    })


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {
        "Content-Type": CONTENT_TYPE_LATEST
    }


if __name__ == "__main__":
    print(f"Starting app | version={VERSION} | chaos={CHAOS_MODE}")
    app.run(host="0.0.0.0", port=5000)