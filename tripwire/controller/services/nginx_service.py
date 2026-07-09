from config import client

UPSTREAM_FILE = "/shared/upstream.conf"


def set_traffic(v1_weight=None, v2_weight=None):

    config = "upstream backend {\n"

    if v1_weight is not None:
        config += f"    server sample-app-v1:5000 weight={v1_weight};\n"

    if v2_weight is not None:
        config += f"    server sample-app-v2:5000 weight={v2_weight};\n"

    config += "}\n"

    with open(UPSTREAM_FILE, "w") as f:
        f.write(config)

    reload_nginx()



def reload_nginx():

    nginx = client.containers.get("tripwire-nginx-1")
    nginx.exec_run("nginx -s reload")