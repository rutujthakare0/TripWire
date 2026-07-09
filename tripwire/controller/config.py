import docker

client = docker.from_env()

IMAGE_NAME   = "tripwire/sample-app:latest"
CANARY_NAME  = "sample-app-v2"
NETWORK_NAME = "tripwire"