# AgentNet nginx

`agentnet.conf` is the production reverse proxy template for the Docker Compose VPS deployment.

It does three important things:

- Proxies REST API traffic to the internal `api:8000` service.
- Preserves WebSocket upgrade headers for `/v1/ws`.
- Blocks public `/metrics` access. Prometheus should scrape metrics from the internal Docker network once Phase 11.7 adds the metrics endpoint and Prometheus config.

TLS is intentionally not embedded in this first template. For a real public host, terminate TLS either in this nginx service with mounted certificates or in an upstream provider such as a cloud load balancer. Do not expose the API container directly to the internet.

