# TripWire

TripWire is an automated canary deployment platform that ships new application
versions with minimal risk. It routes a slice of live traffic to a canary
instance, continuously watches its latency and error rate against the stable
baseline, and automatically promotes or rolls back the release — no manual
intervention required.

---

## How It Works

1. A new version is deployed as a canary alongside the running stable version.
2. Nginx splits traffic 90/10 between baseline and canary.
3. Prometheus scrapes request count, latency, and error metrics from both versions.
4. The Analysis Engine polls those metrics on a fixed interval and evaluates
   canary health against the baseline.
5. **If healthy** for enough consecutive checks → the canary is **promoted**
   to receive 100% of traffic.
6. **If unhealthy** (latency regression or error spike) → traffic is
   **rolled back** to the stable version and the canary is removed.

```
                    +----------------+
                    | Load Generator |
                    +--------+-------+
                             |
                             v
                    +-----------------+
                    |      Nginx      |
                    +--------+--------+
                             |
              +--------------+--------------+
              |                             |
              v                             v
     +------------------+         +------------------+
     |  Sample App v1    |         |  Sample App v2    |
     |    (stable)       |         |    (canary)       |
     +--------+----------+         +---------+----------+
              |                              |
              +--------------+---------------+
                             |
                             v
                       +------------+
                       | Prometheus |
                       +-----+------+
                             |
                             v
                    +------------------+
                    | Analysis Engine  |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    |    Controller    |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    |  Docker Engine   |
                    +------------------+
```

---

## Tech Stack

| Category           | Technology                    |
|---------------------|-------------------------------|
| Backend              | Python, Flask                 |
| Reverse Proxy        | Nginx (weighted upstreams)    |
| Metrics              | Prometheus                    |
| Visualization        | Grafana                       |
| Containerization      | Docker, Docker Compose        |
| Canary Orchestration  | Docker SDK for Python         |

---

## Project Structure

```
tripwire/
├── analysis-engine/     # Monitors Prometheus metrics, decides promote/rollback
├── controller/          # Deploys canaries, manages Nginx traffic weights
├── proxy/                # Nginx config + dynamic upstream.conf
├── sample-app/           # Instrumented Flask app (baseline + canary), supports chaos injection
├── load-generator/       # Continuously sends traffic through Nginx
├── infra/                 # Prometheus scrape config
├── grafana/                # Dashboards + datasource provisioning
├── docker-compose.yml
└── README.md
```

---

## Components

### Sample App
A Flask application exposing:
- `/health` — liveness check
- `/process` — the main traffic-serving endpoint, instrumented with Prometheus metrics
- `/metrics` — Prometheus scrape target

Supports configurable chaos injection via the `CHAOS_MODE` environment variable,
used to simulate failure scenarios and validate that TripWire responds correctly:
- `CHAOS_MODE=latency` — artificially delays responses
- `CHAOS_MODE=errors` — randomly returns HTTP 500s
- `CHAOS_MODE=none` — normal operation (default for the baseline)

### Controller
A Flask service responsible for:
- Deploying canary containers via the Docker SDK
- Health-checking new canaries before shifting traffic
- Writing Nginx's `upstream.conf` and triggering a reload
- Handling promotion and rollback

**Endpoints:**

| Method | Route        | Description                                              |
|--------|--------------|------------------------------------------------------------|
| POST   | `/deploy`    | Deploys a canary and shifts traffic to a 90/10 split. Accepts an optional JSON body: `{"image": "...", "chaos_mode": "latency"}` |
| POST   | `/promote`   | Shifts 100% of traffic to the canary                     |
| POST   | `/rollback`  | Reverts traffic to the stable version and removes the canary |

### Analysis Engine
Runs a background monitoring loop that, on a fixed interval:
- Pulls p95 latency and error rate for both versions from Prometheus
- Triggers **rollback** if canary latency exceeds a configurable multiple of
  baseline latency, or if canary error rate exceeds an absolute threshold
- Triggers **promotion** after a configurable number of consecutive healthy checks

### Prometheus
Scrapes both application versions directly and collects:
- Request count
- Request rate
- Request latency (histogram, used for p95 calculations)
- Error rate

### Grafana
Pre-provisioned dashboard visualizing:
- Request rate
- Request count by version
- P95 latency
- Error rate
- Live traffic distribution between baseline and canary

---

## Running the Project

Clone the repository:

```bash
git clone https://github.com/rutujthakare0/TripWire.git
cd TripWire/tripwire
```

Start all services:

```bash
docker compose up --build
```

## Services

| Service          | URL                     |
|-------------------|--------------------------|
| Sample App         | http://localhost:8080   |
| Controller API      | http://localhost:8000   |
| Prometheus          | http://localhost:9090   |
| Grafana              | http://localhost:3000   |

---

## Chaos Testing

Trigger a canary deploy with induced failure to validate that TripWire
detects and reacts correctly:

```bash
curl -X POST http://localhost:8000/deploy \
  -H "Content-Type: application/json" \
  -d '{"chaos_mode": "latency"}'
```

```bash
curl -X POST http://localhost:8000/deploy \
  -H "Content-Type: application/json" \
  -d '{"chaos_mode": "errors"}'
```

Watch the Analysis Engine's logs to see it detect the regression and trigger
an automatic rollback:

```bash
docker logs -f tripwire-analysis-engine-1
```

---

## Future Improvements

- Kubernetes-native deployment
- Progressive traffic shifting (10% → 25% → 50% → 100%) instead of a single 90/10 step
- Alertmanager integration
- Slack / Discord notifications on promote or rollback
- Deployment history and audit log
- Blue-green deployment strategy as an alternative to canary
- Dynamic Prometheus service discovery instead of static scrape targets

---

## License

MIT License
