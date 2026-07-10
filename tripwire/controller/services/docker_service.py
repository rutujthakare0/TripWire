from services.health_service import wait_for_health
from services.nginx_service import set_traffic
from config import (
    client,
    STABLE_IMAGE,
    CANARY_NAME,
    BASELINE_NAME,
    NETWORK_NAME
)


def get_container(name):
    try:
        return client.containers.get(name)
    except Exception:
        return None


def remove_container(name):
    container = get_container(name)
    if container:
        container.stop()
        container.remove(force=True)


def create_canary(image=None, chaos_mode="none"):
    # Use image from CI pipeline, or fall back to stable image
    canary_image = image or STABLE_IMAGE

    # Remove any existing canary
    remove_container(CANARY_NAME)

    client.containers.run(
        canary_image,
        name=CANARY_NAME,
        detach=True,
        network=NETWORK_NAME,
        environment={
            "APP_VERSION": "v2",
            "CHAOS_MODE": chaos_mode
        }
    )

    healthy = wait_for_health(f"http://{CANARY_NAME}:5000/health")

    if not healthy:
        remove_container(CANARY_NAME)
        return {"status": "failed", "reason": "canary health check timed out"}

    set_traffic(90, 10)

    return {
        "status": "deployed",
        "canary_image": canary_image,
        "split": "90% v1 / 10% v2"
    }


def promote_canary():
    canary = get_container(CANARY_NAME)
    if not canary:
        return {"status": "failed", "message": "No canary running"}

    # Get the image the canary is running so we can promote it
    canary_image_id = canary.image.id

    # Step 1: shift all traffic to canary while we swap baseline
    set_traffic(None, 100)

    # Step 2: tag the canary image as the new stable
    client.images.get(canary_image_id).tag("tripwire/sample-app", tag="stable")

    # Step 3: stop and remove the old baseline
    remove_container(BASELINE_NAME)

    # Step 4: start new baseline with the newly promoted image
    client.containers.run(
        "tripwire/sample-app:stable",
        name=BASELINE_NAME,
        detach=True,
        network=NETWORK_NAME,
        environment={
            "APP_VERSION": "v1",
            "CHAOS_MODE": "none"
        }
    )

    # Step 5: wait for new baseline to be healthy
    wait_for_health(f"http://{BASELINE_NAME}:5000/health")

    # Step 6: shift traffic fully to new baseline and remove canary
    set_traffic(100, None)
    remove_container(CANARY_NAME)

    return {"status": "promoted", "new_stable": "tripwire/sample-app:stable"}


def rollback_canary():
    # Shift all traffic back to baseline and remove canary
    set_traffic(100, None)
    remove_container(CANARY_NAME)
    return {"status": "rolled_back"}