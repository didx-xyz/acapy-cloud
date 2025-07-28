"""Utility functions for resilience testing

This module provides helper functions for:
- Pod monitoring and kubectl operations
- Agent status checking and health monitoring
- Enhanced error handling and logging
"""

import subprocess

from shared.log_config import get_logger

LOGGER = get_logger(__name__)


class LogPatternMonitor:
    """Monitor for specific log patterns that should trigger pod kills"""

    def __init__(self, monitor_script_path: str = "./monitor_and_kill_pod.sh") -> None:
        """Initialize the log pattern monitor"""
        self.monitor_script_path = monitor_script_path
        self.monitor_process = None

    def start_monitoring(self, log_pattern: str | None = None) -> subprocess.Popen:
        """Start log pattern monitoring"""
        LOGGER.info("Starting log pattern monitoring...")

        # If a custom pattern is provided, we could modify the script
        # For now, we'll use the script as-is

        self.monitor_process = subprocess.Popen(
            [self.monitor_script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        LOGGER.info(f"Log monitor started (PID: {self.monitor_process.pid})")
        return self.monitor_process

    def is_monitoring_active(self) -> bool:
        """Check if monitoring process is still active"""
        return self.monitor_process and self.monitor_process.poll() is None

    def stop_monitoring(self):
        """Stop the monitoring process"""
        if self.monitor_process and self.monitor_process.poll() is None:
            LOGGER.info("Stopping log monitor...")
            self.monitor_process.terminate()
            try:
                self.monitor_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.monitor_process.kill()
                self.monitor_process.wait()
            LOGGER.info("Log monitor stopped")

    def get_monitor_output(self) -> tuple[str, str]:
        """Get the output from the monitoring process"""
        if not self.monitor_process:
            return "", ""

        try:
            stdout, stderr = self.monitor_process.communicate(timeout=1)
            return stdout, stderr
        except subprocess.TimeoutExpired:
            return "", ""
