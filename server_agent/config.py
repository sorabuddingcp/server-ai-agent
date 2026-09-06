\
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _csv(name: str, default: str = "") -> List[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


@dataclass(frozen=True)
class Config:
    server_name: str = os.getenv("SERVER_NAME", os.uname().nodename)
    environment: str = os.getenv("ENVIRONMENT", "production")

    health_interval: int = _int("HEALTH_INTERVAL", 60)
    log_interval: int = _int("LOG_INTERVAL", 15)

    cpu_warning: float = _float("CPU_WARNING", 85)
    cpu_critical: float = _float("CPU_CRITICAL", 95)
    memory_warning: float = _float("MEMORY_WARNING", 85)
    memory_critical: float = _float("MEMORY_CRITICAL", 95)
    disk_warning: float = _float("DISK_WARNING", 85)
    disk_critical: float = _float("DISK_CRITICAL", 95)
    load_warning_per_cpu: float = _float("LOAD_WARNING_PER_CPU", 1.50)
    load_critical_per_cpu: float = _float("LOAD_CRITICAL_PER_CPU", 2.50)

    disk_paths: List[str] = field(
        default_factory=lambda: os.getenv("DISK_PATHS", "/").split()
    )
    services: List[str] = field(
        default_factory=lambda: _csv("SERVICES", "nginx,apache2,httpd,ssh,sshd")
    )
    alert_on_missing_service: bool = _bool("ALERT_ON_MISSING_SERVICE", False)

    nginx_error_log: str = os.getenv("NGINX_ERROR_LOG", "/var/log/nginx/error.log")
    apache_error_log: str = os.getenv("APACHE_ERROR_LOG", "/var/log/apache2/error.log")
    apache_rhel_error_log: str = os.getenv("APACHE_RHEL_ERROR_LOG", "/var/log/httpd/error_log")
    web_error_batch_threshold: int = _int("WEB_ERROR_BATCH_THRESHOLD", 1)
    web_error_summary_window_seconds: int = _int("WEB_ERROR_SUMMARY_WINDOW_SECONDS", 300)

    auth_log: str = os.getenv("AUTH_LOG", "/var/log/auth.log")
    auth_log_rhel: str = os.getenv("AUTH_LOG_RHEL", "/var/log/secure")
    ssh_failed_threshold: int = _int("SSH_FAILED_THRESHOLD", 5)
    ssh_failed_window_seconds: int = _int("SSH_FAILED_WINDOW_SECONDS", 300)
    ssh_alert_success: bool = _bool("SSH_ALERT_SUCCESS", True)
    ssh_alert_failed_burst: bool = _bool("SSH_ALERT_FAILED_BURST", True)
    ssh_alert_root_login: bool = _bool("SSH_ALERT_ROOT_LOGIN", True)
    trusted_ssh_networks: List[str] = field(default_factory=lambda: _csv("TRUSTED_SSH_NETWORKS"))

    alert_cooldown_seconds: int = _int("ALERT_COOLDOWN_SECONDS", 900)
    recovery_alerts: bool = _bool("RECOVERY_ALERTS", True)

    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = _int("SMTP_PORT", 587)
    smtp_security: str = os.getenv("SMTP_SECURITY", "starttls").lower()
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from: str = os.getenv("SMTP_FROM", "")
    smtp_to: List[str] = field(default_factory=lambda: _csv("SMTP_TO"))
    smtp_timeout: int = _int("SMTP_TIMEOUT", 20)

    gemini_enabled: bool = _bool("GEMINI_ENABLED", True)
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_timeout_seconds: int = _int("GEMINI_TIMEOUT_SECONDS", 20)

    state_dir: Path = Path(os.getenv("STATE_DIR", "/var/lib/server-ai-agent"))
    log_file: Path = Path(os.getenv("LOG_FILE", "/var/log/server-ai-agent/agent.log"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    def validate(self) -> None:
        errors = []
        if not self.smtp_host:
            errors.append("SMTP_HOST is required")
        if not self.smtp_from:
            errors.append("SMTP_FROM is required")
        if not self.smtp_to:
            errors.append("SMTP_TO must contain at least one recipient")
        if self.smtp_security not in {"starttls", "ssl", "none"}:
            errors.append("SMTP_SECURITY must be starttls, ssl, or none")
        if self.health_interval < 10 or self.log_interval < 2:
            errors.append("Intervals are too aggressive; HEALTH_INTERVAL>=10 and LOG_INTERVAL>=2")
        if errors:
            raise ValueError("; ".join(errors))
