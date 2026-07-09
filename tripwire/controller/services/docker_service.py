from services.health_service import wait_for_health
from config import (
    client,
    IMAGE_NAME,
    CANARY_NAME,
    NETWORK_NAME
)


from services.nginx_service import set_traffic

def get_container(name):
    try:
        return client.containers.get(name)
    except:
        return None


def remove_canary():

    container = get_container(CANARY_NAME)

    if container:
        container.stop()
        container.remove(force=True)


def create_canary():

    existing = get_container(CANARY_NAME)

    if existing:
        remove_canary()

    container = client.containers.run(
        IMAGE_NAME,
        name=CANARY_NAME,
        detach=True,
        network=NETWORK_NAME,
        environment={
            "APP_VERSION": "v2",
            "CHAOS_MODE": "none"
        }
    )

    healthy = wait_for_health(f"http://{CANARY_NAME}:5000/health")

    if not healthy:
        remove_canary()

        return {
            "status": "failed"
        }

    set_traffic(90, 10)

    return {
        "status": "deployed"
    }
def promote_canary():

    if not get_container(CANARY_NAME):
        return {
            "status": "failed",
            "message": "No canary running"
        }

    set_traffic(None, 100)

    return {
        "status": "promoted"
    }


def rollback_canary():

    set_traffic(100, None)

    remove_canary()

    return {
        "status": "rolled_back"
    }