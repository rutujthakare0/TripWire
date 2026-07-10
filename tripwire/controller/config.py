import docker

client = docker.from_env()

STABLE_IMAGE  = "tripwire/sample-app:stable"
CANARY_NAME   = "sample-app-v2"
BASELINE_NAME = "sample-app-v1"
NETWORK_NAME  = "tripwire"