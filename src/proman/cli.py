from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from . import registry, git_ops, runner, ops, new_project, key_manager
from . import search as search_mod
from .config import load_config

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="proman — standardized Git workflow & project launcher.")
console = Console()
err = Console(stderr=True)


def _die(msg: str, code: int = 1) -> None:
    err.print(f"[bold red]{msg}[/bold red]")
    raise typer.Exit(code)


def _fuzzy_find_project(name: str) -> tuple[str, Path] | None:
    data = registry.load()
    if not data:
        _die("Registry is empty.")

    if name in data:
        path = Path(data[name]["path"])
        if path.is_dir() and runner.has_script(path):
            return name, path

    name_lower = name.lower()
    matches = []
    for p_name, entry in data.items():
        if name_lower in p_name.lower():
            path = Path(entry["path"])
            if path.is_dir() and runner.has_script(path):
                matches.append((p_name, path))

    if not matches:
        _die(f"Project '{name}' not found (no exact match, no substring match).")
    
    if len(matches) == 1:
        return matches[0]

    console.print(f"[yellow]Multiple projects match '{name}':[/yellow]")
    for i, (p_name, p_path) in enumerate(matches, 1):
        console.print(f"  {i}. {p_name}  ({p_path})")
    
    choice = Prompt.ask("Select project number", choices=[str(i) for i in range(1, len(matches) + 1)])
    idx = int(choice) - 1
    return matches[idx]


def _resolve_project(name: str) -> Path:
    result = _fuzzy_find_project(name)
    if result is None:
        _die(f"Project '{name}' not found.")
    return result[1]


def _parse_git_url(url: str) -> tuple[str, str, str]:
    s = url.rstrip("/")

    def _map_host(ssh_host: str) -> str:
        if ssh_host.startswith("git-ssh."):
            return "git." + ssh_host[len("git-ssh."):]
        if ssh_host.startswith("git."):
            return ssh_host
        return ssh_host

    m = re.match(r"^ssh://[^@]+@([^:/]+)(?::\d+)?/(.+?)(?:\.git)?$", s)
    if m:
        host, path = m.group(1), m.group(2)
        provider = "github" if host.endswith("github.com") else "gitlab"
        return provider, _map_host(host), path

    m = re.match(r"^git@([^:]+):(.+?)(?:\.git)?$", s)
    if m:
        host, path = m.group(1), m.group(2)
        provider = "github" if host.endswith("github.com") else "gitlab"
        return provider, _map_host(host), path

    if s.startswith(("http://", "https://")):
        p = urlparse(s)
        host = p.hostname or ""
        path = p.path.lstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        provider = "github" if host.endswith("github.com") else "gitlab"
        return provider, host, path

    parts = s.split("/")
    return "gitlab", "", "/".join(parts[-2:])


@app.command()
def integrate(provider: str = typer.Argument(..., help="gitlab or github"),
              hostname: str = typer.Option("gitlab.com", "--hostname", "-H",
                                           help="GitLab host (for self-hosted)")):
    """Configure CLI authentication (glab/gh)."""
    if provider == "gitlab":
        key_manager.integrate_glab(hostname)
    elif provider == "github":
        key_manager.integrate_gh()
    else:
        _die(f"Unknown provider: {provider}. Use 'gitlab' or 'github'.")


@app.command()
def init(url: str = typer.Argument(..., help="Git URL of the project"),
         name: str = typer.Option(None, "--name", "-n"),
         dest: Path = typer.Option(None, "--dest", "-d"),
         duration_key: bool = typer.Option(False, "--duration-key", "-k",
             help="Add SSH key to GitLab/GitHub profile and clone")):
    """Clone a repository, create run.pm.sh, and register it."""
    cfg = load_config()
    project_name = name or Path(url.rstrip("/")).stem.replace(".git", "")
    base = dest or Path(cfg["projects_dir"]).expanduser()
    target = base / project_name
    if target.exists():
        _die(f"'{target}' already exists.")

    provider, api_host, repo_path = _parse_git_url(url)
    key_path = None

    if duration_key:
        if not key_manager.provider_ready(provider, hostname=api_host):
            cli = key_manager.provider_cli_name(provider)
            err.print(f"[yellow]{cli} is not ready for {api_host}.[/yellow]")
            if provider == "gitlab":
                err.print(f"Run: [bold]proman integrate gitlab --hostname {api_host}[/bold]")
            else:
                err.print("Run: [bold]proman integrate github[/bold]")
            if not typer.confirm("Continue without an SSH key?"):
                raise typer.Exit(1)
            duration_key = False

    if duration_key:
        key_path = key_manager.generate(project_name)
        try:
            key_manager.upload(provider, repo_path, key_path,
                               f"proman:{project_name}",
                               hostname=api_host if provider == "gitlab" else None)
            console.print(f"[green]✔[/green] SSH key added to {provider} profile")
        except Exception as e:
            key_manager.cleanup_local(key_path)
            _die(f"upload failed: {e}")

        os.system(f"ssh-add {key_path} 2>/dev/null")

    # Clone
    if duration_key and key_path:
        env = {**os.environ,
               "GIT_SSH_COMMAND": f"ssh -i {key_path} -o IdentitiesOnly=yes"}
        target.parent.mkdir(parents=True, exist_ok=True)
        rc = subprocess.call(["git", "clone", url, str(target)], env=env)
        if rc != 0:
            _die("git clone failed.")
    else:
        if git_ops.clone(url, target) != 0:
            _die("git clone failed.")

    # Branch: try develop, fallback to current
    cfg_branch = cfg["default_branch_name"]
    if git_ops.checkout_branch(target, cfg_branch) != 0:
        current = git_ops.current_branch(target)
        if current:
            console.print(f"[yellow]Branch '{cfg_branch}' does not exist, staying on '{current}'[/yellow]")
            cfg_branch = current
        else:
            _die(f"Could not checkout '{cfg_branch}' or determine current branch.")

    # Ensure run.pm.sh and commit
    runner.ensure_script(target)
    if git_ops.has_uncommitted(target):
        git_ops.save(target, "chore: add run.pm.sh", cfg["remote_name"],
                     cfg_branch, True)

    # Save to registry
    registry.add(project_name, target,
                 provider=provider,
                 deploy_key_id=0,
                 deploy_key_path=str(key_path) if key_path else "",
                 remote=url,
                 api_host=api_host,
                 branch=cfg_branch)
    console.print(f"[green]✔[/green] '{project_name}' ready at {target}")


@app.command()
def new(name: str = typer.Argument(...),
        template: str = typer.Option(None, "--template", "-t"),
        dest: Path = typer.Option(None, "--dest", "-d")):
    """Create a new project from a template."""
    try:
        target = new_project.create(name, template, dest)
    except (FileExistsError, FileNotFoundError) as e:
        _die(str(e))
    registry.add(name, target)
    console.print(f"[green]✔[/green] created {target}")


@app.command()
def save(message: str = typer.Argument(...),
         project: str = typer.Option(None, "--project", "-p")):
    """Commit and push changes (add + commit + push)."""
    cfg = load_config()
    path = _resolve_project(project) if project else Path.cwd()
    branch = git_ops.current_branch(path) or cfg["default_branch_name"]
    rc = git_ops.save(path, message, cfg["remote_name"], branch,
                      cfg["auto_push"] == "true")
    raise typer.Exit(rc)


@app.command()
def sync(project: str = typer.Option(None, "--project", "-p")):
    """Pull with rebase and push."""
    cfg = load_config()
    path = _resolve_project(project) if project else Path.cwd()
    branch = git_ops.current_branch(path) or cfg["default_branch_name"]
    raise typer.Exit(git_ops.sync(path, cfg["remote_name"], branch))


@app.command()
def run(name: str = typer.Argument(...)):
    """Run the project's run.pm.sh script."""
    raise typer.Exit(runner.run(_resolve_project(name)))


@app.command()
def repath(new_path: Path = typer.Argument(...)):
    """Re-bind a project to a new path."""
    target = new_path.expanduser().resolve()
    if not target.is_dir():
        _die(f"'{target}' is not a directory")
    name = typer.prompt("Project name")
    registry.add(name, target)
    console.print(f"[green]✔[/green] '{name}' -> {target}")


@app.command()
def move(name: str = typer.Argument(...), new_path: Path = typer.Argument(...)):
    """Move a project folder and update the registry."""
    try:
        result = ops.move_project(name, new_path)
    except (FileNotFoundError, FileExistsError) as e:
        _die(str(e))
    console.print(f"[green]✔[/green] moved to {result}")


@app.command()
def destroy(name: str = typer.Argument(...),
            yes: bool = typer.Option(False, "--yes", "-y",
                help="Skip confirmation prompts")):
    """Remove a project from the registry (and optionally delete its folder and SSH key)."""
    data = registry.load()
    if name not in data:
        _die(f"Project '{name}' is not registered.")

    entry = data[name]
    path = Path(entry["path"])
    provider = entry.get("provider")
    key_path_str = entry.get("deploy_key_path")
    api_host = entry.get("api_host")

    if not yes:
        if not typer.confirm(f"Remove '{name}' from the registry?"):
            raise typer.Exit(0)
        if path.is_dir() and typer.confirm(f"Delete local folder '{path}'?"):
            shutil.rmtree(path, ignore_errors=True)
        if key_path_str and provider:
            key_path = Path(key_path_str)
            if key_path.exists():
                if typer.confirm(f"Remove SSH key from {provider} profile?"):
                    try:
                        key_manager.revoke(provider, entry.get("remote", ""), key_path, hostname=api_host)
                    except Exception as e:
                        err.print(f"[yellow]Warning: could not revoke SSH key: {e}[/yellow]")
                key_manager.cleanup_local(key_path)
    else:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        if key_path_str and provider:
            key_path = Path(key_path_str)
            if key_path.exists():
                try:
                    key_manager.revoke(provider, entry.get("remote", ""), key_path, hostname=api_host)
                except Exception:
                    pass
                key_manager.cleanup_local(key_path)

    registry.remove(name)
    console.print(f"[green]✔[/green] '{name}' removed.")


@app.command()
def search(name: str = typer.Argument(...)):
    """Find a lost project by name or language."""
    cfg = load_config()
    root = Path(cfg["projects_dir"]).expanduser()
    hit = search_mod.find_by_name(root, name)
    if hit:
        console.print(f"[green]found:[/green] {hit}")
        return
    hits = search_mod.find_by_lang(root, name)
    if not hits:
        console.print("nothing found")
        raise typer.Exit(1)
    for h in hits:
        console.print(f"{h.path}  (score={h.score}, "
                      f"{search_mod.fmt_time(h.last_modified)})")


@app.command("list")
def list_cmd():
    """Show all registered projects."""
    data = registry.load()
    if not data:
        console.print("Registry is empty.")
        return
    table = Table(title="Registered projects")
    table.add_column("Name"); table.add_column("Path"); table.add_column("Exists")
    table.add_column("Provider"); table.add_column("Key")
    for name, entry in sorted(data.items()):
        p = Path(entry["path"])
        exists = "✔" if p.is_dir() else "✘"
        prov = str(entry.get("provider") or "—")
        key = str(entry.get("deploy_key_id") or "—")
        table.add_row(name, entry["path"], exists, prov, key)
    console.print(table)


@app.command()
def doctor():
    """Check the health of all registered projects."""
    data = registry.load()
    if not data:
        console.print("Registry is empty."); return
    table = Table(title="proman doctor")
    table.add_column("Name"); table.add_column("Branch")
    table.add_column("Status"); table.add_column("Problems")
    healths = ops.doctor_all(data)
    for h in healths:
        status = "[green]ok[/green]" if h.ok else "[red]fail[/red]"
        table.add_row(h.name, h.branch or "—", status,
                      "; ".join(h.problems) or "—")
    console.print(table)
    if any(not h.ok for h in healths):
        raise typer.Exit(1)


@app.command()
def stats():
    """Show statistics for all projects."""
    data = registry.load()
    if not data:
        console.print("Registry is empty."); return
    table = Table(title="proman stats")
    table.add_column("Name"); table.add_column("Files", justify="right")
    table.add_column("Size", justify="right"); table.add_column("Last commit")
    for name, entry in sorted(data.items()):
        p = Path(entry["path"])
        if not p.is_dir():
            table.add_row(name, "—", "—", "missing"); continue
        files, size = ops.tree_stat(p)
        last = git_ops.last_commit_ts(p) if git_ops.is_repo(p) else 0.0
        table.add_row(name, str(files), ops.human_size(size),
                      search_mod.fmt_time(last))
    console.print(table)


@app.command()
def backup():
    """Archive all projects to the backup directory."""
    data = registry.load()
    if not data:
        console.print("Registry is empty."); return
    archives = ops.backup_all(data)
    for a in archives:
        console.print(f"[green]✔[/green] {a}")
    if not archives:
        console.print("Nothing to archive.")


@app.command()
def export(dest: Path = typer.Argument(..., help="Destination JSON file")):
    """Export the registry to JSON."""
    ops.export_registry(registry.load(), dest)
    console.print(f"[green]✔[/green] exported → {dest}")


@app.command(name="import")
def import_cmd(src: Path = typer.Argument(..., help="JSON registry file")):
    """Import the registry from JSON."""
    if not src.is_file():
        _die(f"'{src}' not found.")
    data = ops.import_registry(src)
    current = registry.load()
    current.update(data)
    registry.save(current)
    console.print(f"[green]✔[/green] imported {len(data)} project(s)")


if __name__ == "__main__":
    app()