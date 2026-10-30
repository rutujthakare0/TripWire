"""
Tripwire Data Collector -- writes RAW measurements only, no stats/guessing.

Run this on your machine. It appends one JSON line per completed trial to
tripwire_raw_data.jsonl as it goes (so a crash on trial 6 doesn't lose
trials 1-5). When you're done, send me that file and I'll compute the
medians / summary from your actual numbers.

DIFFERENCES FROM THE EARLIER VERSION
-------------------------------------
- Detection is now POLLING-based instead of streaming logs. Streaming
  (container.logs(stream=True, follow=True)) can hang forever on some
  Docker Desktop setups depending on how logs are piped -- polling
  container.logs(since=..., until=...) every second is slower per-check
  but far more reliable and easier to debug if something's wrong.
- Health check already fixed to use python's urllib instead of curl
  (the sample-app image has no curl installed).
- Every trial's raw numbers are written to disk immediately, not held
  in memory until the end.
- No median/summary calculation here at all -- that's intentional, so
  there's zero risk of me or the script inventing anything. You send me
  the raw file, I do the arithmetic on your real numbers.

ONE-TIME SETUP (same as before)
---------------------------------
1. nginx.conf needs $upstream_addr logging -- already patched for you
   in the previous message (nginx.conf.patched). Rebuild:
       docker compose build nginx && docker compose up -d nginx
2. pip install docker requests
3. docker compose up -d   (full stack running, load-generator keeps
   traffic flowing on its own)
4. Run this from the tripwire/ repo root:
       python tripwire_collect.py
"""

import time
import json
from pathlib import Path
from datetime import datetime, timezone

import docker
import requests

# ----------------------- CONFIG -----------------------

NUM_TRIALS = 24
FAULT_TYPES = ["latency", "errors"]

CONTROLLER_URL = "http://localhost:8000"
IMAGE_NAME = "tripwire/sample-app:stable"   # matches actual docker-compose.yml build tag
CANARY_NAME = "sample-app-v2"
BASELINE_NAME = "sample-app-v1"
NETWORK_NAME = "tripwire"                   # matches actual docker-compose.yml networks.tripwire.name
NGINX_CONTAINER = "tripwire-nginx"          # matches actual container_name in docker-compose.yml
ANALYSIS_ENGINE_CONTAINER = "tripwire-analysis-engine-1"

UPSTREAM_CONF_HOST_PATH = Path("proxy/upstream.conf")
RAW_OUTPUT_FILE = Path("tripwire_raw_data.jsonl")

DETECTION_POLL_INTERVAL = 1.0
DETECTION_TIMEOUT = 120
ROLLBACK_TIMEOUT = 60
COOLDOWN_BETWEEN_TRIALS = 65  # > analyzer's 1m rate() window + 1 check
                              # interval, so each trial starts on a
                              # clean metric slate with zero bleed-over
                              # from the previous trial's chaos samples

client = docker.from_env()


# ----------------------- Nginx traffic -----------------------

def set_traffic(v1_weight=None, v2_weight=None):
    config = "upstream backend {\n"
    if v1_weight is not None:
        config += f"    server {BASELINE_NAME}:5000 weight={v1_weight};\n"
    if v2_weight is not None:
        config += f"    server {CANARY_NAME}:5000 weight={v2_weight};\n"
    config += "}\n"
    UPSTREAM_CONF_HOST_PATH.write_text(config)
    nginx = client.containers.get(NGINX_CONTAINER)
    nginx.exec_run("nginx -s reload")


# ----------------------- Canary lifecycle -----------------------

def get_container(name):
    try:
        return client.containers.get(name)
    except docker.errors.NotFound:
        return None


def remove_canary():
    c = get_container(CANARY_NAME)
    if c:
        c.stop()
        c.remove(force=True)


def deploy_chaos_canary(chaos_mode):
    remove_canary()

    container = client.containers.run(
        IMAGE_NAME,
        name=CANARY_NAME,
        detach=True,
        network=NETWORK_NAME,
        environment={"APP_VERSION": "v2", "CHAOS_MODE": chaos_mode},
    )

    health_check_cmd = (
        "python -c \""
        "import urllib.request,sys;"
        "sys.exit(0 if urllib.request.urlopen('http://localhost:5000/health',timeout=2).status==200 else 1)"
        "\""
    )

    healthy = False
    last_output = None
    start = time.time()
    while time.time() - start < 30:
        try:
            res = container.exec_run(health_check_cmd)
            last_output = res.output.decode(errors="ignore")
            if res.exit_code == 0:
                healthy = True
                break
        except Exception as e:
            last_output = str(e)
        time.sleep(1)

    if not healthy:
        print(f"  [debug] last health check output: {last_output}")
        remove_canary()
        raise RuntimeError("canary failed health check")

    container.reload()
    ip = container.attrs["NetworkSettings"]["Networks"][NETWORK_NAME]["IPAddress"]
    return ip


def reset_baseline():
    try:
        requests.post(f"{CONTROLLER_URL}/rollback", timeout=5)
    except Exception:
        pass
    remove_canary()
    set_traffic(100, None)


# ----------------------- Detection + rollback (polling) -----------------------

def wait_for_detection_polling(since_ts, timeout=DETECTION_TIMEOUT):
    """
    Polls analysis-engine logs every DETECTION_POLL_INTERVAL seconds,
    checking the full log window since since_ts for "ROLLBACK triggered".
    Returns the wall-clock time it was FIRST OBSERVED (not necessarily
    the exact moment it happened, but bounded by poll interval -- real
    and honest, just slightly coarse-grained).
    """
    since_dt = datetime.fromtimestamp(since_ts, tz=timezone.utc)
    deadline = time.time() + timeout

    while time.time() < deadline:
        # Re-resolve by name each poll instead of caching the container
        # object -- if analysis-engine gets rebuilt/recreated mid-trial
        # (new container ID, same name), this picks up the new one
        # instead of 404ing against a stale ID.
        engine = client.containers.get(ANALYSIS_ENGINE_CONTAINER)
        logs = engine.logs(since=since_dt, stream=False).decode(errors="ignore")
        if "ROLLBACK triggered" in logs:
            return time.time()
        time.sleep(DETECTION_POLL_INTERVAL)

    raise TimeoutError(f"no detection within {timeout}s")


def wait_for_rollback_complete(timeout=ROLLBACK_TIMEOUT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if get_container(CANARY_NAME) is None:
            return time.time()
        time.sleep(0.5)
    raise TimeoutError("rollback did not complete in time")


# ----------------------- Blast radius (raw counts, no % math left to guesswork) -----------------------

def count_blast_radius(canary_ip, t_start, t_end):
    nginx = client.containers.get(NGINX_CONTAINER)
    since_dt = datetime.fromtimestamp(t_start, tz=timezone.utc)
    until_dt = datetime.fromtimestamp(t_end, tz=timezone.utc)
    raw = nginx.logs(since=since_dt, until=until_dt, stream=False).decode(errors="ignore")

    total = 0
    canary_hits = 0
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        upstream_field = parts[1]
        if upstream_field == "-":
            continue
        total += 1
        if canary_ip in upstream_field:
            canary_hits += 1

    return total, canary_hits


# ----------------------- Trial runner -----------------------

def append_result(record):
    with open(RAW_OUTPUT_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def run_trial(trial_num, chaos_mode):
    print(f"\n--- Trial {trial_num} ({chaos_mode}) ---")
    record = {"trial": trial_num, "chaos_mode": chaos_mode, "status": "failed"}

    try:
        reset_baseline()
        time.sleep(2)

        t0 = time.time()
        canary_ip = deploy_chaos_canary(chaos_mode)
        set_traffic(90, 10)
        print(f"  chaos canary ({chaos_mode}) deployed at {t0:.2f}, ip={canary_ip}")

        t1 = wait_for_detection_polling(since_ts=t0)
        print(f"  detected at {t1:.2f}  (raw latency: {t1 - t0:.2f}s)")

        t2 = wait_for_rollback_complete()
        print(f"  rollback complete at {t2:.2f}  (raw duration: {t2 - t1:.2f}s)")

        total_req, canary_hits = count_blast_radius(canary_ip, t0, t2)
        print(f"  nginx requests in window: {total_req}, canary hits: {canary_hits}")

        record.update({
            "status": "ok",
            "t0_injection": t0,
            "t1_detection": t1,
            "t2_rollback_complete": t2,
            "detection_latency_s": round(t1 - t0, 3),
            "rollback_duration_s": round(t2 - t1, 3),
            "total_recovery_s": round(t2 - t0, 3),
            "canary_ip": canary_ip,
            "total_requests_in_window": total_req,
            "canary_hits_in_window": canary_hits,
        })

    except (TimeoutError, RuntimeError) as e:
        record["error"] = str(e)
        print(f"  [trial {trial_num} failed: {e}]")

    finally:
        reset_baseline()

    append_result(record)
    return record


def main():
    print(f"Writing raw results to {RAW_OUTPUT_FILE.resolve()}")
    for i in range(1, NUM_TRIALS + 1):
        chaos_mode = FAULT_TYPES[(i - 1) % len(FAULT_TYPES)]
        run_trial(i, chaos_mode)
        time.sleep(COOLDOWN_BETWEEN_TRIALS)

    print(f"\nDone. Send {RAW_OUTPUT_FILE.resolve()} back and the real numbers get computed from it.")


if __name__ == "__main__":
    main()