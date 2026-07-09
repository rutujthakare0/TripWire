import time

from config import CHECK_INTERVAL

from services.prometheus_service import (
    get_latency,
    get_error_rate
)

from services.controller_service import (
    rollback,
    promote
)

LATENCY_RATIO = 1.5
ERROR_RATIO = 2
STABLE_CHECKS = 4


def monitor():

    stable_count = 0

    while True:

        v1_latency = get_latency("v1") or 0.0
        v2_latency = get_latency("v2") or 0.0

        v1_error = get_error_rate("v1") or 0.0
        v2_error = get_error_rate("v2") or 0.0

        print(
            f"v1_latency={v1_latency}, "
            f"v2_latency={v2_latency}, "
            f"v1_error={v1_error}, "
            f"v2_error={v2_error}"
        )

        # No canary traffic yet
        if v2_latency == 0:
            stable_count = 0
            time.sleep(CHECK_INTERVAL)
            continue

        rollback_required = False

        if v1_latency > 0:
            if (v2_latency / v1_latency) > LATENCY_RATIO:
                rollback_required = True

        if v1_error > 0:
            if (v2_error / v1_error) > ERROR_RATIO:
                rollback_required = True

        if rollback_required:

            print("Rollback triggered")

            rollback()

            stable_count = 0

        else:

            stable_count += 1

            print(f"Stable checks: {stable_count}/{STABLE_CHECKS}")

            if stable_count >= STABLE_CHECKS:

                print("Promoting canary")

                promote()

                stable_count = 0

        time.sleep(CHECK_INTERVAL)