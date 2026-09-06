\
from __future__ import annotations

import argparse
import signal
import sys
import time

from .ai import AIAnalyzer
from .config import Config
from .emailer import EmailNotifier
from .filetail import FileTailer
from .logging_setup import setup_logging
from .monitors.health import HealthMonitor
from .monitors.ssh import SSHMonitor
from .monitors.web import WebLogMonitor
from .state import StateStore


class Agent:
    def __init__(self, cfg: Config):
        cfg.validate()
        self.cfg = cfg
        self.log = setup_logging(cfg.log_file, cfg.log_level)
        self.state = StateStore(cfg.state_dir)
        self.tailer = FileTailer(self.state, self.log)
        self.health = HealthMonitor(cfg, self.state, self.log)
        self.web = WebLogMonitor(cfg, self.tailer, self.log)
        self.ssh = SSHMonitor(cfg, self.state, self.tailer, self.log)
        self.ai = AIAnalyzer(cfg, self.log)
        self.email = EmailNotifier(cfg, self.log)
        self.running = True

    def stop(self, *_):
        self.running = False

    def dispatch(self, incident):
        # Security logins are intentionally unique per user/IP but still cooldown-protected.
        if not self.state.should_alert(
            incident.fingerprint, self.cfg.alert_cooldown_seconds
        ):
            self.log.info("Suppressed duplicate alert: %s", incident.fingerprint)
            return

        # AI is enrichment only; alerting never depends on it.
        if incident.severity in {"WARNING", "CRITICAL"}:
            incident.ai_analysis = self.ai.analyze(incident)

        self.email.send(incident)

    def run_once(self):
        for incident in self.health.collect():
            self.dispatch(incident)
        for incident in self.web.collect():
            self.dispatch(incident)
        for incident in self.ssh.collect():
            self.dispatch(incident)

    def run(self):
        self.log.info(
            "Server AI Agent started server=%s env=%s", self.cfg.server_name, self.cfg.environment
        )
        last_health = 0.0
        last_logs = 0.0

        while self.running:
            now = time.monotonic()
            try:
                if now - last_health >= self.cfg.health_interval:
                    for incident in self.health.collect():
                        self.dispatch(incident)
                    last_health = now

                if now - last_logs >= self.cfg.log_interval:
                    for incident in self.web.collect():
                        self.dispatch(incident)
                    for incident in self.ssh.collect():
                        self.dispatch(incident)
                    last_logs = now
            except Exception:
                self.log.exception("Unhandled monitor-cycle error")

            time.sleep(1)

        self.ai.close()
        self.log.info("Server AI Agent stopped")


def main():
    parser = argparse.ArgumentParser(description="Read-only AI server health/security monitor")
    parser.add_argument("--once", action="store_true", help="Run one monitoring cycle and exit")
    parser.add_argument("--test-email", action="store_true", help="Send a test email and exit")
    parser.add_argument("--check-config", action="store_true", help="Validate config and exit")
    args = parser.parse_args()

    try:
        agent = Agent(Config())
    except Exception as exc:
        print(f"Configuration/startup error: {exc}", file=sys.stderr)
        return 2

    if args.check_config:
        print("Configuration OK")
        return 0
    if args.test_email:
        return 0 if agent.email.send_test() else 1
    if args.once:
        agent.run_once()
        return 0

    signal.signal(signal.SIGTERM, agent.stop)
    signal.signal(signal.SIGINT, agent.stop)
    agent.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
