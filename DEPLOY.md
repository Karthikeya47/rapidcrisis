# Deploying

Two parts: the **model** runs on Nebius Token Factory, and the **app** is one Docker container that can run anywhere.
The live demo is hosted on **Render**; running it on Nebius AI Cloud is described below as an alternative.

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

## 2. Run it on Render (live demo)

In Render: **New → Web Service**, connect the GitHub repo, then:

- Root directory: `backend`
- Runtime: Docker (Render builds `backend/Dockerfile`)
- Environment variable: `NEBIUS_API_KEY` = your Token Factory key
- Render sets `PORT` itself; the container already listens on it

Render serves it over HTTPS, so the microphone works in the browser. On the free plan the service sleeps after
about 15 idle minutes: the first visit afterwards takes up to a minute and starts with a fresh demo state.

## 3. Get the container image (for other hosts)

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

## 4. Alternative: run it on Nebius AI Cloud (Serverless endpoint)

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

When it's running, copy its public HTTPS URL. Open it, check the header says
**"Nemotron 3 Super dispatches · Ultra reviews"**, and try an example.

## Alternative: a Nebius CPU VM

Create a small CPU VM with a public IP in the Nebius console, then:

```bash
sudo apt-get update && sudo apt-get install -y docker.io
sudo docker run -d --restart always -p 80:8080 \
  -e NEBIUS_API_KEY=<your key> ghcr.io/<user>/rapidcrisis:latest
```

The demo is then at `http://<vm-public-ip>/`. Note: browsers only allow the microphone on HTTPS or localhost,
so on plain HTTP voice won't work — typing still does. The Serverless endpoint gives you HTTPS.
