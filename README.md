<<<<<<< HEAD
# server-ai-agent
server-ai-agent monitoring server nginx,ssh,logs
=======
\
# Server AI Agent — Phase 1

A read-only Linux monitoring/security agent for Ubuntu/Debian and RHEL-family servers.

## Monitors

- CPU, RAM, 1-minute load normalized by CPU count
- Disk usage
- systemd services
- Nginx error log
- Apache error log
- Successful SSH logins
- Root SSH logins
- Failed SSH-login bursts / simple brute-force detection
- Alert recovery events
- SMTP email, including Amazon SES SMTP
- Optional Gemini incident analysis
- Persistent file cursors, deduplication and cooldowns
- systemd daemon + service hardening
- local rotating application log + logrotate

The agent performs **no remediation**. It does not block IP addresses, restart services, kill processes, change firewall rules, or modify system configuration.

## 1. Copy project to the server

```bash
scp -r server-ai-agent user@server:/tmp/
ssh user@server
cd /tmp/server-ai-agent
```

## 2. Install

```bash
chmod +x install.sh uninstall.sh
sudo ./install.sh
```

The installer creates:

```text
/opt/server-ai-agent
/etc/server-ai-agent/server-ai-agent.env
/var/lib/server-ai-agent
/var/log/server-ai-agent
/etc/systemd/system/server-ai-agent.service
/etc/logrotate.d/server-ai-agent
```

It also creates an unprivileged `server-agent` system user and adds it to log-reading groups when available.

## 3. Configure

```bash
sudo nano /etc/server-ai-agent/server-ai-agent.env
```

At minimum set:

```dotenv
SERVER_NAME=prod-web-01

SMTP_HOST=email-smtp.ap-south-1.amazonaws.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=YOUR_SES_SMTP_USERNAME
SMTP_PASSWORD=YOUR_SES_SMTP_PASSWORD
SMTP_FROM=verified-sender@example.com
SMTP_TO=your-alert-address@example.com

GEMINI_ENABLED=true
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-2.5-flash
```

Important: Amazon SES SMTP credentials are not the same as ordinary AWS access-key credentials.

If AI enrichment is not wanted:

```dotenv
GEMINI_ENABLED=false
GEMINI_API_KEY=
```

All monitoring and email alerts still work.

## 4. Check log permissions

Ubuntu/Debian typically uses:

```text
/var/log/auth.log
/var/log/nginx/error.log
/var/log/apache2/error.log
```

RHEL/Rocky/Alma typically uses:

```text
/var/log/secure
/var/log/nginx/error.log
/var/log/httpd/error_log
```

Verify the agent can read the files actually present:

```bash
sudo -u server-agent test -r /var/log/auth.log && echo auth-readable
sudo -u server-agent test -r /var/log/secure && echo secure-readable
sudo -u server-agent test -r /var/log/nginx/error.log && echo nginx-readable
sudo -u server-agent test -r /var/log/apache2/error.log && echo apache-readable
sudo -u server-agent test -r /var/log/httpd/error_log && echo httpd-readable
```

If your distro has unusual log permissions, grant **read-only** access with a group or ACL rather than running the whole monitor as root.

Example ACL:

```bash
sudo setfacl -m u:server-agent:r /var/log/secure
```

If log rotation replaces the file, configure the log-creating daemon/rotation policy to preserve access for the monitoring user rather than repeatedly applying an ACL manually.

## 5. Validate configuration

```bash
sudo -u server-agent bash -c '
  set -a
  source /etc/server-ai-agent/server-ai-agent.env
  set +a
  /opt/server-ai-agent/venv/bin/python -m server_agent --check-config
'
```

Expected:

```text
Configuration OK
```

## 6. Send a test email

```bash
sudo -u server-agent bash -c '
  set -a
  source /etc/server-ai-agent/server-ai-agent.env
  set +a
  /opt/server-ai-agent/venv/bin/python -m server_agent --test-email
'
```

## 7. Start

```bash
sudo systemctl start server-ai-agent
sudo systemctl status server-ai-agent
```

Watch:

```bash
sudo journalctl -u server-ai-agent -f
```

Application log:

```bash
sudo tail -f /var/log/server-ai-agent/agent.log
```

## 8. Test safely

### Health threshold

Temporarily lower a threshold in the environment file:

```dotenv
CPU_WARNING=1
```

Restart:

```bash
sudo systemctl restart server-ai-agent
```

After testing, restore the normal threshold.

### SSH login

SSH into the host from another terminal. A successful login should generate an alert when:

```dotenv
SSH_ALERT_SUCCESS=true
```

The first time the agent sees a log file, it starts at EOF. This intentionally prevents historical log entries from generating hundreds of alerts immediately after installation.

### Nginx

Use an existing harmless test environment/log entry rather than deliberately breaking production. The monitor begins from the end of the file and reacts only to newly appended error entries.

## Alert deduplication

Default cooldown:

```dotenv
ALERT_COOLDOWN_SECONDS=900
```

So a persistent CPU alert is not emailed every minute. SSH events use fingerprints based on event type/user/source IP. Failed-login bursts use the source IP.

## Trusted SSH networks

```dotenv
TRUSTED_SSH_NETWORKS=10.0.0.0/8,192.168.0.0/16,203.0.113.10/32
```

A successful login from a trusted range is INFO. An untrusted successful login is WARNING. Root logins can be CRITICAL.

This classification is only a local policy signal; it is not geolocation or behavioral anomaly detection.

## Important production notes

### Amazon SES

Use the SMTP endpoint for the same SES Region you configured. STARTTLS commonly uses port 587. SES requires TLS for SMTP connections. Verify the sender identity and make sure the Region/account is allowed to send to the destination you need.

### SSH logging

This Phase-1 package parses `/var/log/auth.log` and `/var/log/secure`. On systems configured to keep SSH events only in journald, enable the distro's normal persistent auth logging or extend the collector to the systemd journal.

### Secrets

The environment file is installed mode `0600`:

```bash
sudo stat /etc/server-ai-agent/server-ai-agent.env
```

Do not commit the real environment file to Git.

For larger deployments, store secrets in AWS Secrets Manager, GCP Secret Manager, Vault, or equivalent and inject them during deployment.

### systemd hardening

The unit uses:

- dedicated non-login account
- `NoNewPrivileges=true`
- `ProtectSystem=strict`
- `ProtectHome=true`
- restricted write paths
- kernel/control-group protection
- automatic restart on failure

It intentionally needs outbound network access for SMTP and Gemini.

## Operations

Restart:

```bash
sudo systemctl restart server-ai-agent
```

Logs:

```bash
sudo journalctl -u server-ai-agent --since "1 hour ago"
```

Disable:

```bash
sudo systemctl disable --now server-ai-agent
```

Uninstall service files while preserving config/state/logs:

```bash
sudo ./uninstall.sh
```

## Directory structure

```text
server-ai-agent/
├── .env.example
├── README.md
├── install.sh
├── uninstall.sh
├── requirements.txt
├── server_agent/
│   ├── __init__.py
│   ├── __main__.py
│   ├── agent.py
│   ├── ai.py
│   ├── config.py
│   ├── emailer.py
│   ├── filetail.py
│   ├── logging_setup.py
│   ├── models.py
│   ├── state.py
│   └── monitors/
│       ├── __init__.py
│       ├── health.py
│       ├── ssh.py
│       └── web.py
├── systemd/
│   └── server-ai-agent.service
├── logrotate/
│   └── server-ai-agent
└── tests/
    └── test_ssh.py
```
>>>>>>> origin/master
