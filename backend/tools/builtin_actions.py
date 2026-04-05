"""
Built-in action tools — email, notifications, HTTP requests, clipboard, screenshot.
These give the agent real capabilities without needing to write credential-handling code.
"""
import asyncio
import os
import json
import logging
from typing import Any

log = logging.getLogger("openclaw.actions")
HOME = os.path.expanduser("~")


async def send_email(
    to: str,
    subject: str,
    body: str,
    smtp_host: str = "",
    smtp_port: int = 587,
    smtp_user: str = "",
    smtp_password: str = "",
    from_addr: str = "",
) -> dict:
    """Send email via SMTP. Falls back to stored credentials if not provided."""
    from core.credentials import get_credential

    # Use stored credentials as fallback
    host = smtp_host or get_credential("smtp", "host") or "smtp.gmail.com"
    port = smtp_port or int(get_credential("smtp", "port") or "587")
    user = smtp_user or get_credential("smtp", "user")
    password = smtp_password or get_credential("smtp", "password")
    sender = from_addr or user

    if not user or not password:
        return {
            "error": "SMTP credentials not configured. Go to Settings → Integrations and add your SMTP credentials.",
            "hint": "For Gmail: use your email + an App Password (not your regular password). Enable 2FA first at myaccount.google.com/security"
        }

    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(user, password)
            server.sendmail(sender, to, msg.as_string())

        log.info("Email sent to %s", to)
        return {"success": True, "to": to, "subject": subject}
    except Exception as e:
        return {"error": str(e)}


async def send_notification(title: str, message: str, sound: bool = True) -> dict:
    """Send a macOS system notification."""
    try:
        sound_str = "default" if sound else "none"
        script = f'display notification "{message}" with title "{title}" sound name "{sound_str}"'
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode != 0:
            return {"error": stderr.decode().strip()}
        return {"success": True, "title": title, "message": message}
    except Exception as e:
        return {"error": str(e)}


async def http_request(
    url: str,
    method: str = "GET",
    headers: dict = None,
    body: str = "",
    timeout: int = 30,
) -> dict:
    """Make an HTTP request. Useful for webhooks, APIs, etc."""
    if not url.startswith(("http://", "https://")):
        return {"error": "Only http/https URLs allowed"}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                method.upper(),
                url,
                headers=headers or {},
                content=body.encode() if body else None,
            )
            return {
                "status": resp.status_code,
                "ok": resp.status_code < 400,
                "body": resp.text[:4000],
                "headers": dict(resp.headers),
            }
    except Exception as e:
        return {"error": str(e)}


async def take_screenshot(save_path: str = "") -> dict:
    """Take a screenshot and save it."""
    if not save_path:
        save_path = os.path.join(HOME, "Desktop", "screenshot.png")
    try:
        proc = await asyncio.create_subprocess_exec(
            "screencapture", "-x", save_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=10)
        if os.path.exists(save_path):
            return {"success": True, "path": save_path}
        return {"error": "Screenshot failed"}
    except Exception as e:
        return {"error": str(e)}


async def get_clipboard() -> dict:
    """Get current clipboard contents."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pbpaste",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        return {"content": stdout.decode("utf-8", errors="replace")[:4000]}
    except Exception as e:
        return {"error": str(e)}


async def set_clipboard(text: str) -> dict:
    """Set clipboard contents."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pbcopy",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(input=text.encode()), timeout=5)
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


async def run_applescript(script: str) -> dict:
    """Run an AppleScript. Powerful for Mac automation."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        return {
            "stdout": stdout.decode().strip(),
            "stderr": stderr.decode().strip(),
            "exit_code": proc.returncode,
        }
    except Exception as e:
        return {"error": str(e)}


async def run_shell(command: str, timeout: int = 30) -> dict:
    """Run a shell command. Full system access."""
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ},
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "stdout": stdout.decode()[:4000],
            "stderr": stderr.decode()[:1000],
            "exit_code": proc.returncode,
        }
    except asyncio.TimeoutError:
        return {"error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}


async def open_app(app_name: str) -> dict:
    """Open a macOS application by name."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "open", "-a", app_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode != 0:
            return {"error": stderr.decode().strip() or f"Could not open {app_name}"}
        return {"success": True, "app": app_name}
    except Exception as e:
        return {"error": str(e)}


async def open_url(url: str) -> dict:
    """Open a URL in the default browser or app."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "open", url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=10)
        return {"success": True, "url": url}
    except Exception as e:
        return {"error": str(e)}
