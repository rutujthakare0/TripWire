import time
import requests


def wait_for_health(url, timeout=30):

    start = time.time()

    while time.time() - start < timeout:

        try:
            response = requests.get(url, timeout=2)

            if response.status_code == 200:
                return True

        except Exception:
            pass

        time.sleep(1)

    return False