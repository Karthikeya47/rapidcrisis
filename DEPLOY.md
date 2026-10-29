# Deploying on Nebius

Two parts: the **model** (Nebius Token Factory) and the **app** (a Docker container on Nebius AI Cloud).

## 1. Get a Token Factory API key

1. Sign in at https://tokenfactory.nebius.com
2. Create an API key.
3. In the model list, confirm the exact ID of **Nemotron 3 Super** (expected: `nvidia/nemotron-3-super-120b-a12b`).
   If it differs, set `NEBIUS_MODEL` to the ID shown there.

Quick check from your laptop:

```bash
curl https://api.tokenfactory.nebius.com/v1/chat/completions \
  -H "Authorization: Bearer $NEBIUS_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"nvidia/nemotron-3-super-120b-a12b","messages":[{"role":"user","content":"Say OK"}]}'
```

## 2. Get the container image

Pushing to `main` on GitHub runs `.github/workflows/ci.yml`, which runs the tests and publishes:

```
ghcr.io/<github-username-lowercase>/rapidcrisis:latest
```

Then on GitHub: your profile → **Packages** → `rapidcrisis` → **Package settings** → change visibility to **Public**
(so Nebius can pull it without credentials).

No GitHub Actions? Build and push it yourself:

```bash
cd backend
docker build --platform linux/amd64 -t ghcr.io/<user>/rapidcrisis:latest .
docker push ghcr.io/<user>/rapidcrisis:latest
```

## 3. Run it on Nebius AI Cloud (Serverless endpoint)

Console: **Serverless AI → Endpoints → Create endpoint**

- Image: `ghcr.io/<user>/rapidcrisis:latest`
- Container port: `8080`
- Platform: CPU only (no GPU needed — the model runs on Token Factory)
- Disk: 20 GiB
- Environment variable: `NEBIUS_API_KEY` = your key (use a secret if offered)
- Authentication: none (so judges can open the demo link)

Or with the Nebius CLI:

```bash
nebius ai endpoint create \
  --name rapidcrisis \
  --image ghcr.io/<user>/rapidcrisis:latest \
  --container-port 8080 \
  --env "NEBIUS_API_KEY=<your key>" \
  --platform cpu-d3 \
  --preset 2vcpu-8gb \
  --disk-size 20Gi
```

When it's running, copy its public HTTPS URL. Open it, check the header badge says
**"Brain: NVIDIA nemotron-3-super-120b-a12b"**, and try an example.

## Fallback: a Nebius CPU VM

Create a small CPU VM with a public IP in the Nebius console, then:

```bash
sudo apt-get update && sudo apt-get install -y docker.io
sudo docker run -d --restart always -p 80:8080 \
  -e NEBIUS_API_KEY=<your key> ghcr.io/<user>/rapidcrisis:latest
```

The demo is then at `http://<vm-public-ip>/`. Note: browsers only allow the microphone on HTTPS or localhost,
so on plain HTTP voice won't work — typing still does. The Serverless endpoint gives you HTTPS.
