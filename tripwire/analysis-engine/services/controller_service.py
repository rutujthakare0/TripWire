import requests

from config import CONTROLLER_URL


def promote():

    requests.post(f"{CONTROLLER_URL}/promote")


def rollback():

    requests.post(f"{CONTROLLER_URL}/rollback")