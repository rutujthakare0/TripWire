import requests

from config import PROMETHEUS_URL


def query(promql):

    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": promql}
    )

    return response.json()


def get_latency(version):

    query_str = f"""
histogram_quantile(
0.95,
sum(rate(http_request_duration_seconds_bucket{{version="{version}"}}[1m])) by (le))
"""

    try:
        data = query(query_str)
        result = data["data"]["result"]

        if not result:
            return 0.0

        return float(result[0]["value"][1])

    except Exception as e:
        print(f"[get_latency:{version}] query failed: {e}")
        return 0.0


def get_error_rate(version):

    query_str = f"""
rate(http_requests_total{{version="{version}",status="500"}}[1m])
/
rate(http_requests_total{{version="{version}"}}[1m])
"""

    try:
        data = query(query_str)
        result = data["data"]["result"]

        if not result:
            return 0.0

        return float(result[0]["value"][1])

    except Exception as e:
        print(f"[get_error_rate:{version}] query failed: {e}")
        return 0.0