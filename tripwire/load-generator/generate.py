import requests
import time
import random

URL = "http://localhost:5000/process"

while True:
    try:
        r = requests.get(URL)
        print(r.json())
    except Exception as e:
        print("error:", e)

    time.sleep(random.uniform(0.1, 0.5))