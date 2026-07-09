import requests
import random
import time

URL="http://nginx/process"

while True:
    try:
        r = requests.get(URL)
        print(r.status_code)
    except Exception as e:
        print(e)

    time.sleep(random.uniform(0.1,0.5))