from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()
err = Console(stderr=True)

SSH_DIR = Path.home() / ".ssh" / "proman"


def _run(cmd: list[str], input: str | None = None,
         cwd: Path | None = None,
         env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, input=input, cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, env=env,
    )


def _glab_env(hostname: str | None) -> dict | None:
    if not hostname:
        return None
    return {**os.environ, "GITLAB_HOST": hostname}


def cli_installed(name: str) -> bool:
    return shutil.which(name) is not None


def glab_authenticated(hostname: str = "gitlab.com") -> bool:
    if not cli_installed("glab"):
        return False
    r = _run(["glab", "auth", "status", "--hostname", hostname])
    out = r.stdout + r.stderr
    if "No token found" in out or "401" in out or "could not authenticate" in out:
        return False
    return "Logged in" in out or "Token found" in out


def gh_authenticated() -> bool:
    if not cli_installed("gh"):
        return False
    r = _run(["gh", "auth", "status"])
    return r.returncode == 0 and "Logged in" in (r.stdout + r.stderr)


def provider_ready(provider: str, hostname: str | None = None) -> bool:
    if provider == "gitlab":
        return glab_authenticated(hostname or "gitlab.com")
    if provider == "github":
        return gh_authenticated()
    return False


def provider_cli_name(provider: str) -> str:
    return "glab" if provider == "gitlab" else "gh"


def provider_install_hint(provider: str) -> str:
    return "sudo pacman -S glab" if provider == "gitlab" else "sudo pacman -S github-cli"


def generate(project: str) -> Path:
    SSH_DIR.mkdir(parents=True, exist_ok=True)
    key = SSH_DIR / project
    if key.exists():
        return key
    r = _run([
        "ssh-keygen", "-t", "ed25519", "-N", "", "-C",
        f"proman:{project}", "-f", str(key),
    ])
    if r.returncode != 0:
        raise RuntimeError(f"ssh-keygen failed: {r.stderr.strip()}")
    return key


def public_key(key: Path) -> str:
    return (key.with_suffix(key.suffix + ".pub")).read_text().strip()


def cleanup_local(key: Path) -> None:
    for p in (key, key.with_suffix(key.suffix + ".pub")):
        if p.exists():
            p.unlink()


def upload(provider: str, repo: str, key: Path, title: str,
           hostname: str | None = None) -> int:
    pub = key.with_suffix(key.suffix + ".pub")
    if provider == "gitlab":
        r = _run(
            ["glab", "ssh-key", "add", str(pub), "-t", title, "--replace"],
            env=_glab_env(hostname),
        )
        if r.returncode != 0:
            raise RuntimeError(f"glab ssh-key add failed: {r.stderr.strip()}")
        return 0
    if provider == "github":
        r = _run(["gh", "ssh-key", "add", str(pub), "-t", title])
        if r.returncode != 0:
            raise RuntimeError(f"gh ssh-key add failed: {r.stderr.strip()}")
        return 0
    raise ValueError(f"unknown provider: {provider}")


def revoke(provider: str, repo: str, key_path: Path,
           hostname: str | None = None) -> None:
    """Removes the SSH key from the user's GitLab/GitHub profile."""
    pub = key_path.with_suffix(key_path.suffix + ".pub")
    if not pub.exists():
        return
    pub_content = pub.read_text().strip()
    if provider == "gitlab":
        cmd = ["glab", "ssh-key", "list"]
        r = _run(cmd, env=_glab_env(hostname))
        for line in r.stdout.splitlines():
            if pub_content in line:
                parts = line.split()
                for p in parts:
                    if p.isdigit():
                        _run(["glab", "ssh-key", "delete", p], env=_glab_env(hostname))
                        return
    elif provider == "github":
        r = _run(["gh", "ssh-key", "list"])
        for line in r.stdout.splitlines():
            if pub_content in line:
                parts = line.split()
                for p in parts:
                    if p.isdigit():
                        _run(["gh", "ssh-key", "delete", p])
                        return


def integrate_glab(hostname: str = "gitlab.com") -> None:
    import typer
    if glab_authenticated(hostname):
        console.print(f"[green]✔[/green] glab is already configured for {hostname}")
        return
    if not cli_installed("glab"):
        err.print("[yellow]glab is not installed.[/yellow]")
        err.print(f"Install it with: [bold]{provider_install_hint('gitlab')}[/bold]")
        raise SystemExit(1)

    err.print(f"[bold]How to get a GitLab token ({hostname}):[/bold]")
    err.print(f"1. Open: https://{hostname}/-/user_settings/personal_access_tokens")
    err.print("2. Generate token -> scope: [bold]api[/bold]")
    err.print("3. Copy the token (it is shown only once)")
    token = typer.prompt("Token", hide_input=True)

    r = _run(["glab", "auth", "login", "--hostname", hostname, "--stdin"],
             input=token)
    if r.returncode != 0:
        err.print(f"[red]glab auth login failed:[/red] {r.stderr.strip()}")
        raise SystemExit(1)
    if not glab_authenticated(hostname):
        err.print("[red]Token was accepted, but glab is still not authenticated.[/red]")
        raise SystemExit(1)
    console.print(f"[green]✔[/green] glab configured for {hostname}")


def integrate_gh() -> None:
    if gh_authenticated():
        console.print("[green]✔[/green] gh is already configured")
        return
    if not cli_installed("gh"):
        err.print("[yellow]gh is not installed.[/yellow]")
        err.print(f"Install it with: [bold]{provider_install_hint('github')}[/bold]")
        raise SystemExit(1)
    err.print("[bold]Starting interactive gh login…[/bold]")
    r = subprocess.run(["gh", "auth", "login"])
    if r.returncode != 0:
        raise SystemExit(1)
    console.print("[green]✔[/green] gh configured")