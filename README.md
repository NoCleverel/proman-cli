# proman

CLI for Git workflow, project launcher, lost project search, and deploy keys.

## Installation

### Arch Linux / CachyOS (from source)

Since AUR registration is temporarily closed, you can build and install `proman` directly from this repository:

```bash
git clone https://github.com/cleverelhome-cloud/proman-cli.git
cd proman-cli
makepkg -si
```
## Quick start

    proman integrate gitlab --hostname gitlab.com
    proman init git@gitlab.com:user/repo.git --duration-key

## Commands

| Command | Description |
|---|---|
| `proman integrate gitlab\|github` | Configure glab/gh (prompts for token) |
| `proman init <url> [--duration-key]` | Clone repo, create branch and `run.pm.sh` |
| `proman new <name> [--template t]` | Create new project from template |
| `proman save "<msg>" [-p name]` | add + commit + push |
| `proman sync [-p name]` | pull --rebase + push |
| `proman run <name>` | Run project's `run.pm.sh` |
| `proman repath <path>` | Re-bind project to new path |
| `proman move <name> <new-path>` | Move folder and update registry |
| `proman destroy <name>` | Remove project from registry |
| `proman search <name>` | Find lost project |
| `proman list` | List registered projects |
| `proman doctor` | Check project health |
| `proman stats` | Show project statistics |
| `proman backup` | Archive projects |
| `proman export` / `proman import` | Transfer registry |

## Config

`~/.config/proman/config` (or `/etc/proman/config`):

    [proman]
    default_branch_name=develop
    remote_name=origin
    auto_push=true
    projects_dir=~/Projects
    templates_dir=~/.config/proman/templates
    backup_dir=~/.local/share/proman/backups

## Registry

`~/.local/share/proman/projects.json` (old `proj-path.conf` is migrated automatically).
