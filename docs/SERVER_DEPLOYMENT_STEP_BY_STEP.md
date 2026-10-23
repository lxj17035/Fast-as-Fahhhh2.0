# Step-by-step: Docker on Ubuntu → Cloudflare Tunnel → dashboard

## Your target

Open **https://hackathon.nailstore.online/** from your computer and reach the
QuoteFlow dashboard running on your Ubuntu server.

This is a standalone guide. Docker is already installed. Follow the numbered
steps in order; you do not need to install Python, Node, pnpm, PostgreSQL, or
Laragon on Ubuntu. Docker supplies the application runtimes and database.

| Item | Value |
| --- | --- |
| Repository | `https://github.com/lxj17035/Fast-as-Fahhhh2.0.git` |
| Branch | `feature/frontend` |
| Server project directory | `~/apps/Fast-as-Fahhhh2.0` |
| Website | `https://hackathon.nailstore.online/` |
| Cloudflare tunnel name | `quoteflow-hackathon` |
| Tunnel's origin service | **HTTP `web:8080`** |
| Database | PostgreSQL 16 in Docker |

The dashboard retains simulated Sales/PM roles. Cloudflare Access limits entry
to your team; it does not assign PM authority inside the app. Use this as a
supervised demo with fictional customer data.

```mermaid
flowchart LR
    Browser["Browser: https://hackathon.nailstore.online"] --> CF["Cloudflare HTTPS + Access login"]
    CF --> Tunnel["Cloudflare Tunnel"]
    subgraph Server["Your Ubuntu server / Docker Compose"]
        Connector["cloudflared container"] --> Web["web:8080 / Nginx + dashboard"]
        Web --> API["api / Python on shared localhost:8004"]
        API --> DB["db:5432 / PostgreSQL"]
        DB --> Disk["Persistent Docker volume"]
    end
    Tunnel --> Connector
```

There are three places where you will work:

- **Your computer:** SSH into Ubuntu and later open the website in your browser.
- **Ubuntu SSH terminal:** run every `bash` block below.
- **Cloudflare dashboard:** complete the explicitly labelled browser steps.

Do not paste the complete document into a terminal. Run one command block at a
time, check its result, then continue.

## 1. Connect to your Ubuntu server

**On your computer**, replace the username and IP address with your SSH details:

```powershell
ssh ubuntu@YOUR_SERVER_IP
```

For a server that uses an SSH key:

```powershell
ssh -i "C:\Users\YOUR_WINDOWS_USER\.ssh\YOUR_KEY" ubuntu@YOUR_SERVER_IP
```

Use whichever login method already works for your server. Once connected, the
following commands run on Ubuntu:

```bash
whoami
pwd
cat /etc/os-release
```

Expected: your Linux username and Ubuntu version. Your Windows project directory
and Laragon installation are not used by the server.

## 2. Verify your existing Docker installation

**On Ubuntu:**

```bash
sudo docker version
sudo docker compose version
sudo systemctl is-active docker
```

Expected:

- Docker shows both Client and Server information.
- `docker compose` reports a version. Use a recent Compose plugin supporting
  `up --wait` and `depends_on.restart` (at least Compose 2.17).
- The service is `active`.

If Docker is installed but stopped:

```bash
sudo systemctl enable --now docker
```

If only the Compose plugin is missing and Docker's official APT repository is
already configured:

```bash
sudo apt-get update
sudo apt-get install -y docker-compose-plugin
sudo docker compose version
```

If APT cannot find that package, follow the repository configuration in
[Docker's official Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/)
before installing the plugin. You do not need to reinstall a working Docker Engine.

Install the small command-line tools used by this guide:

```bash
sudo apt-get update
sudo apt-get install -y git curl openssl nano
```

## 3. Download the project

For the **first installation** on this server:

```bash
mkdir -p ~/apps
cd ~/apps
git clone --branch feature/frontend --single-branch https://github.com/lxj17035/Fast-as-Fahhhh2.0.git
cd Fast-as-Fahhhh2.0
```

If that project directory already contains the repository, use this instead of
cloning again:

```bash
cd ~/apps/Fast-as-Fahhhh2.0
git status --short
git switch feature/frontend
git pull --ff-only origin feature/frontend
```

If Git reports local edits or a conflict, review them before continuing; do not
reset or delete existing files to force an update. For a private repository, use
your existing GitHub SSH access rather than putting a token in the clone URL.

Check the branch and required files:

```bash
git branch --show-current
ls -l Dockerfile frontend/Dockerfile compose.yaml compose.cloudflare.yaml
ls -l deploy/nginx.conf deploy/nginx-webhook.conf deploy/frontend-config.js
```

Expected branch: `feature/frontend`. All listed files must exist.

## 4. Create the Ubuntu server's private .env

Stay inside `~/apps/Fast-as-Fahhhh2.0`. This block creates a new `.env` only if
one does not already exist. It generates two different private random values
directly into the file, without printing them:

```bash
umask 077
if [ ! -e .env ]; then
    cat > .env <<EOF
POSTGRES_PASSWORD=$(openssl rand -hex 32)
TELEGRAM_WEBHOOK_SECRET=$(openssl rand -hex 32)
WEB_PORT=8080
DATABASE_URL=
AI_PROVIDER=manual
ENABLE_DEMO_APPROVAL=false
TELEGRAM_BOT_TOKEN=
RUNPOD_API_KEY=
OPENAI_API_KEY=
CLOUDFLARE_TUNNEL_TOKEN=
EOF
fi
chmod 600 .env
nano .env
```

If `.env` already existed, review it in nano and ensure it has these entries:

```dotenv
POSTGRES_PASSWORD=YOUR_PRIVATE_RANDOM_HEX_PASSWORD
TELEGRAM_WEBHOOK_SECRET=YOUR_DIFFERENT_PRIVATE_RANDOM_HEX_SECRET
WEB_PORT=8080
DATABASE_URL=
AI_PROVIDER=manual
ENABLE_DEMO_APPROVAL=false
CLOUDFLARE_TUNNEL_TOKEN=
```

The uppercase values above are explanations, not passwords to copy. To generate
replacement values when setting up a new database, run `openssl rand -hex 32`
separately for each field and paste the results privately into nano.

In nano: **Ctrl+O**, **Enter** saves; **Ctrl+X** exits.

What these settings mean:

| Setting | What to do |
| --- | --- |
| POSTGRES_PASSWORD | Keep the generated hex value; the API and database use it together |
| TELEGRAM_WEBHOOK_SECRET | Required for API startup even before Telegram is configured |
| DATABASE_URL | Leave blank here; Compose supplies the private `db:5432` connection |
| WEB_PORT | Keep 8080 for the diagnostics commands below |
| AI_PROVIDER | `manual` starts the dashboard without paid AI requests |
| ENABLE_DEMO_APPROVAL | Keep false until a supervised team send test is configured |
| CLOUDFLARE_TUNNEL_TOKEN | Fill this after creating the tunnel in step 6 |

Keep `.env` on the server and out of Git, chat, and screenshots. Do not copy the
Windows Laragon DATABASE_URL: the database lives in a Docker service named `db`.
Do not change POSTGRES_PASSWORD after the database volume has been initialized
without also rotating the password in PostgreSQL.

## 5. Configure Cloudflare and protect your dashboard

**In your browser, open the Cloudflare dashboard.**

### 5.1 Check your domain

Select the `nailstore.online` zone and confirm its status is **Active**. If it is
not active, set the nameservers at the registrar to the nameservers Cloudflare
assigns, then wait for activation. Keep existing unrelated DNS records.

You will use `hackathon.nailstore.online`. For this tunnel setup you do not need
an A record pointing the hostname at the Ubuntu server IP.

### 5.2 Create the staff Access application

Complete this before publishing the hostname:

1. Open **Zero Trust / Cloudflare One**. Complete the team/account setup if it is
   your first visit.
2. In identity provider/login-method settings, enable **One-time PIN**, or use
   your already configured identity provider.
3. Open **Access controls → Applications → Add an application**.
4. Select a **Self-hosted** application and add a public hostname.
5. Name it `QuoteFlow dashboard`.
6. Set the hostname to **hackathon.nailstore.online**. Leave the path blank so
   the protection covers the whole site, including API and PDF requests.
7. Add an **Allow** policy. Under **Include → Emails**, enter your own email
   address and the exact email addresses of authorized teammates.
8. Permit the One-time PIN login method and save the application/policy.

Do not use an Everyone or Bypass policy for this staff hostname. Selecting the
OTP login method alone does not restrict who can sign in; the email allowlist
does that. This is an external gate for the demo, not a change to Python roles.

Cloudflare's menu wording may differ slightly. References:
[create an Access application](https://developers.cloudflare.com/learning-paths/clientless-access/access-application/create-access-app/)
and [email access policies](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/common-policies/).

## 6. Create the Cloudflare Tunnel

**In the Cloudflare dashboard:**

1. Open **Networking → Tunnels**. Some accounts show this under
   **Networks → Connectors → Cloudflare Tunnels** in Zero Trust.
2. Select **Create tunnel** and choose **Cloudflared**.
3. Enter the tunnel name **quoteflow-hackathon** and save.
4. Select the **Docker** connector instructions.
5. Find the long connector token after `--token` in the displayed command.
6. Copy only that token. Do not run the separate `docker run` command displayed
   by Cloudflare; the project's Compose file will start that container.

**Back in your Ubuntu SSH terminal:**

```bash
cd ~/apps/Fast-as-Fahhhh2.0
nano .env
```

Replace the blank token entry with your real private value:

```dotenv
CLOUDFLARE_TUNNEL_TOKEN=YOUR_PRIVATE_TOKEN_FROM_CLOUDFLARE
```

Save with **Ctrl+O**, **Enter**, then **Ctrl+X**. Paste the token only into this
private file. A tunnel connector token is different from a Cloudflare API token.
You do not need to install cloudflared separately on Ubuntu.

Cloudflare documents the Docker connector in its
[tunnel setup guide](https://developers.cloudflare.com/tunnel/get-started/)
and the token environment variable in
[run parameters](https://developers.cloudflare.com/tunnel/reference/run-parameters/).

## 7. Build and start the project

**On Ubuntu, from the project directory:**

```bash
cd ~/apps/Fast-as-Fahhhh2.0

# Validate the merged configuration without printing secret values.
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml config --quiet

# Build the app and start all four containers in the background.
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml up -d --build --wait --wait-timeout 180

# Inspect the result.
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml ps
```

The first build can take several minutes while images and packages download.
`--wait-timeout` applies to service readiness; it is not a build-time estimate.

Expected containers:

| Service | Expected state | Purpose |
| --- | --- | --- |
| db | Running / healthy | Persistent PostgreSQL storage |
| web | Running / healthy | Nginx, dashboard, and PDF.js assets |
| api | Running / healthy | Existing Python API |
| cloudflared | Running | Connection from Docker to Cloudflare |

If a command fails, inspect the relevant service before proceeding:

```bash
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml logs --tail=100 db
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml logs --tail=100 api
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml logs --tail=100 web
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml logs --tail=100 cloudflared
```

Review logs locally; do not share credentials or customer content. Do not run
`docker compose config` without `--quiet` in shared logs because it expands secrets.

## 8. Verify the app locally on Ubuntu

Before testing the public domain, check the server-side app:

```bash
curl --fail http://127.0.0.1:8080/healthz
curl --fail http://127.0.0.1:8080/api/health
curl --fail http://127.0.0.1:8080/config.js
curl --fail -I http://127.0.0.1:8080/
curl --fail -I http://127.0.0.1:8080/vendor/pdfjs/build/pdf.worker.mjs
```

Expected results:

- `/healthz` returns `ok`.
- `/api/health` returns HTTP 200 with the backend's JSON health response.
- `/config.js` includes `export const API_BASE_URL = '';`.
- `/` returns HTTP 200 and an HTML content type.
- The PDF worker returns HTTP 200 with a JavaScript content type.

The empty API base is correct: the browser calls the same domain's `/api/...`,
and Nginx forwards that to the Python API. Do not change it to localhost:8004
or a Docker service name in the browser configuration.

Now check the tunnel connector in Cloudflare. It should show **Healthy / Connected**.
A running cloudflared container alone does not prove that its token or connection
works; inspect its logs and the dashboard state.

## 9. Connect the subdomain to the dashboard

**In Cloudflare, open the `quoteflow-hackathon` tunnel.**

Go to **Routes / Published application routes / Public hostnames**, then add a
published application with these exact settings:

| Field | Value to enter |
| --- | --- |
| Subdomain | `hackathon` |
| Domain | `nailstore.online` |
| Path | Leave blank |
| Service type | **HTTP** |
| Service URL | **web:8080** |

If the interface has a single complete service address field, enter:

```text
http://web:8080
```

Save the route. With a normal Cloudflare-managed DNS zone, the dashboard creates
the tunnel's DNS record. If it reports that `hackathon` already has a conflicting
record, review and replace only that hostname's record before saving again.
There is no need to create an A record pointing at your server. See
[Cloudflare routing](https://developers.cloudflare.com/tunnel/concepts/routing/).

Why this exact address matters:

- `web` is the Nginx container's Compose service name.
- `8080` is Nginx's port inside Docker.
- `localhost:8080` would point at the cloudflared container itself.
- `https://web:8080` is incorrect because this internal listener uses HTTP.
- The external browser URL still uses HTTPS through Cloudflare.

Confirm the zone's edge SSL certificate is active. Enable **Always Use HTTPS**
for the intended hostname if you need HTTP visits redirected to HTTPS. Do not
add a Cache Everything rule: API responses and versioned PDF previews need the
latest saved data. Review any existing custom cache rules for this hostname.

## 10. Open your dashboard

**On your own computer**, open a private/incognito browser window and visit:

```text
https://hackathon.nailstore.online/
```

Expected sequence:

1. Cloudflare Access asks for your approved email address.
2. You receive a one-time login code, or use the configured identity provider.
3. After signing in, the QuoteFlow enquiry inbox opens.
4. The app shows Connected, and Settings opens successfully.

Check an unapproved account is denied. The entire hostname should be protected,
not only the homepage. A command-line request to the public API without an Access
session can return a login redirect or denial instead of JSON; use step 8 for
the origin API health check.

A new database normally has an empty Telegram inbox. Starting the website does
not copy Windows/Laragon records, create fake inbox rows, register a Telegram
webhook, or send a message. You can visit the dashboard successfully before
configuring AI and Telegram.

## 11. Network and persistence details

The tunnel makes outbound connections, so this setup does not need inbound
80/443, inbound 8080, or router port forwarding. Keep your existing SSH access
for administration; do not change SSH/firewall settings blindly.

If outbound traffic is restricted, allow the tunnel's required **7844 TCP/UDP**
connections and normal DNS/HTTPS needed for Docker image downloads and providers.
Use [Cloudflare's firewall requirements](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/tunnel-with-firewall/)
for the current destination list.

PostgreSQL data and saved PDFs live in the named volume
**quoteflow_postgres_data**. Rebuilding containers preserves that volume. Do not
run `down -v` or volume-prune commands as routine maintenance; they can destroy
the database. The server starts with a separate database from Laragon.

## 12. Commands for normal maintenance

Always run these from the repository root and keep **both `-f` arguments**.

### Check status and recent logs

```bash
cd ~/apps/Fast-as-Fahhhh2.0
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml ps
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml logs --tail=100
```

### Back up before updating

```bash
cd ~/apps/Fast-as-Fahhhh2.0
umask 077
mkdir -p output/backups
chmod 700 output/backups
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml exec -T db pg_dump -U quoteflow -d quoteflow -Fc > "output/backups/quoteflow-$(date -u +%Y%m%dT%H%M%SZ).dump"
ls -lh output/backups
```

Check pg_dump exits successfully and the file is nonempty. Keep a private off-server
copy. For recovery, restore into a separate empty database and verify it before
switching the application; do not overwrite active records as a first experiment.

### Pull reviewed project updates and rebuild

```bash
cd ~/apps/Fast-as-Fahhhh2.0
git status --short
git pull --ff-only origin feature/frontend
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml pull cloudflared
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml up -d --build --force-recreate --wait --wait-timeout 180
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml ps
curl --fail http://127.0.0.1:8080/api/health
```

Recreating the complete stack keeps the API joined to Nginx's current shared
network namespace. Avoid recreating only web in isolation.

### Stop and start without deleting the database

```bash
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml stop
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml start
```

Closing SSH does not stop these detached containers. Restart policies are set
to `unless-stopped`; after a server reboot, check Docker is active, all services
are running, and the Cloudflare connector is healthy. A manually stopped service
may need starting again.

### After editing .env

```bash
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml up -d --force-recreate --wait --wait-timeout 180
```

This applies new container environment values. Changing a database password in
`.env` does not rotate an existing database's stored password. Coordinate that
change separately and keep backups.

## 13. Troubleshooting

| Problem | Check or action |
| --- | --- |
| `docker: command not found` | Docker is unavailable in this server session; confirm you are SSH'd into the correct host |
| `docker compose` not recognized | Install/update the Compose plugin in step 2 |
| Permission denied on Docker socket | Use the `sudo docker ...` commands shown here |
| POSTGRES_PASSWORD or webhook secret required | Review `.env` in the repository root; both values must be nonblank |
| CLOUDFLARE_TUNNEL_TOKEN required | Complete step 6; the value must be the connector token, not an API key |
| Database password authentication failed | Verify the original initialized volume's password; do not erase the volume to fix a config typo |
| API unhealthy | Read `api` and `db` logs; confirm database health and webhook-secret format |
| Local port 8080 already allocated | Check `sudo ss -ltnp 'sport = :8080'`; choose a free WEB_PORT in `.env` and adjust local curl commands. The tunnel origin stays `web:8080` |
| Cloudflare 1033 / tunnel disconnected | Check connector logs, token, and outbound network connectivity |
| Cloudflare 502 | Confirm origin is **HTTP web:8080**, all containers are in this Compose project, and the origin health check passes |
| Domain does not resolve | Check zone activation, the exact hostname, and the tunnel DNS record |
| SSL/certificate error | Check Cloudflare's edge certificate is active for the hostname |
| No login code or access denied | Check OTP login settings and the exact email allowlist |
| API returns HTML after some time | Access session may have expired; sign in again before retrying normal reads |
| Empty inbox | Fresh database has no Telegram enquiries; website hosting can still be working |
| Browser calls localhost:8004 | Verify `/config.js` contains the empty API base, rebuild the Docker frontend, and reload |

To collect diagnostics locally:

```bash
cd ~/apps/Fast-as-Fahhhh2.0
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml ps
sudo docker compose -f compose.yaml -f compose.cloudflare.yaml logs --tail=100 api web cloudflared
curl --fail http://127.0.0.1:8080/api/health
```

Review/redact logs before sharing them. Do not share the contents of `.env`.

## 14. Optional later work: AI and Telegram

Your requested hosting outcome is complete when the domain opens the protected
dashboard and its API connection works. AI/Telegram provider setup is a separate
integration step; keep the required credentials private.

When ready, follow [the optional Telegram hostname instructions](CLOUDFLARE_UBUNTU.md)
and [controlled live verification](LIVE_TEST.md). The existing overlay supports
`hackathon-telegram.nailstore.online` → HTTP `web:8081`, an endpoint-only listener,
so Telegram does not need to pass the staff's interactive login.

## Completion check

- [ ] The Ubuntu repository is on `feature/frontend`.
- [ ] Server `.env` is private and contains the generated database/webhook secrets and tunnel token.
- [ ] db, web, and api are healthy; cloudflared is running and connected in Cloudflare.
- [ ] Local `/api/health` returns HTTP 200.
- [ ] The published route is `hackathon.nailstore.online` → **HTTP web:8080**.
- [ ] An approved user can sign in and visit the dashboard; an unapproved user is denied.
- [ ] The dashboard shows Connected and Settings opens.

These are actions to perform on your server/account. Writing this guide does not
claim that Docker images, Cloudflare DNS/Access, or the live domain were deployed
or verified remotely. The backend source is unchanged.
