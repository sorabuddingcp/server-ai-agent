\
#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer as root: sudo ./install.sh"
  exit 1
fi

APP_DIR=/opt/server-ai-agent
ETC_DIR=/etc/server-ai-agent
STATE_DIR=/var/lib/server-ai-agent
LOG_DIR=/var/log/server-ai-agent
SERVICE_USER=server-agent

if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip ca-certificates
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y python3 python3-pip ca-certificates
else
  echo "Unsupported package manager. Install Python 3, pip, venv, and CA certificates manually."
  exit 1
fi

if ! getent group "$SERVICE_USER" >/dev/null 2>&1; then
  groupadd --system "$SERVICE_USER"
fi
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --gid "$SERVICE_USER" --home "$STATE_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

# Add log-reading groups only if they exist.
for grp in adm systemd-journal; do
  if getent group "$grp" >/dev/null; then
    usermod -a -G "$grp" "$SERVICE_USER"
  fi
done

mkdir -p "$APP_DIR" "$ETC_DIR" "$STATE_DIR" "$LOG_DIR"
cp -a server_agent requirements.txt "$APP_DIR"/
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [[ ! -f "$ETC_DIR/server-ai-agent.env" ]]; then
  cp .env.example "$ETC_DIR/server-ai-agent.env"
  chmod 600 "$ETC_DIR/server-ai-agent.env"
  echo
  echo "Created $ETC_DIR/server-ai-agent.env"
  echo "EDIT THIS FILE before starting the service."
fi

chown -R root:root "$APP_DIR"
chmod -R go-w "$APP_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$STATE_DIR" "$LOG_DIR"

cp systemd/server-ai-agent.service /etc/systemd/system/server-ai-agent.service

# Remove SupplementaryGroups that do not exist (important on minimal RHEL systems).
groups=()
for grp in adm systemd-journal; do
  if getent group "$grp" >/dev/null; then groups+=("$grp"); fi
done
if [[ ${#groups[@]} -eq 0 ]]; then
  sed -i '/^SupplementaryGroups=/d' /etc/systemd/system/server-ai-agent.service
else
  sed -i "s/^SupplementaryGroups=.*/SupplementaryGroups=${groups[*]}/" /etc/systemd/system/server-ai-agent.service
fi

cp logrotate/server-ai-agent /etc/logrotate.d/server-ai-agent
systemctl daemon-reload
systemctl enable server-ai-agent

echo
echo "Installation complete."
echo "1. Edit: sudo nano $ETC_DIR/server-ai-agent.env"
echo "2. Validate: sudo -u $SERVICE_USER env \$(grep -v '^#' $ETC_DIR/server-ai-agent.env | xargs) $APP_DIR/venv/bin/python -m server_agent --check-config"
echo "3. Test email: sudo systemctl start server-ai-agent && sudo journalctl -u server-ai-agent -n 50 --no-pager"
echo "4. Or manually: sudo -u $SERVICE_USER bash -c 'set -a; source $ETC_DIR/server-ai-agent.env; set +a; $APP_DIR/venv/bin/python -m server_agent --test-email'"
