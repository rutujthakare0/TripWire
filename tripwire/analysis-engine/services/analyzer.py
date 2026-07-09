import time
from config import CHECK_INTERVAL
from services.prometheus_service import get_latency, get_error_rate
from services.controller_service import rollback, promote

LATENCY_RATIO   = 1.5   # canary latency > 1.5x baseline → rollback
ERROR_THRESHOLD = 0.05  # canary error rate > 5% absolute → rollback
STABLE_CHECKS   = 4     # 4 consecutive healthy checks → promote


def monitor():
    stable_count = 0

    while True:
        v1_latency = get_latency("v1") or 0.0
        v2_latency = get_latency("v2") or 0.0
        v1_error   = get_error_rate("v1") or 0.0
        v2_error   = get_error_rate("v2") or 0.0

        print(
            f"v1_latency={v1_latency:.4f}, v2_latency={v2_latency:.4f}, "
            f"v1_error={v1_error:.4f}, v2_error={v2_error:.4f}"
        )

        # No canary traffic yet — skip this cycle
        if v2_latency == 0.0:
            stable_count = 0
            time.sleep(CHECK_INTERVAL)
            continue

        rollback_required = False

        # Check 1: latency regression
        if v1_latency > 0 and (v2_latency / v1_latency) > LATENCY_RATIO:
            print(f"Latency regression detected: v2={v2_latency:.4f}s vs v1={v1_latency:.4f}s")
            rollback_required = True

        # Check 2: absolute error rate threshold
        # Does NOT depend on v1 having errors — catches the 0% → 40% case
        if v2_error > ERROR_THRESHOLD:
            print(f"Error rate too high: v2={v2_error:.4f} (threshold={ERROR_THRESHOLD})")
            rollback_required = True

        if rollback_required:
            print("ROLLBACK triggered")
            rollback()
            stable_count = 0
        else:
            stable_count += 1
            print(f"Stable check {stable_count}/{STABLE_CHECKS}")

            if stable_count >= STABLE_CHECKS:
                print("PROMOTE — canary is healthy")
                promote()
                stable_count = 0

        time.sleep(CHECK_INTERVAL)