# Installation

## Requirements

- [Docker](https://docs.docker.com/get-docker/)
- An [Anthropic API key](https://console.anthropic.com/) or Claude Code login

## Setup

Clone the repository and build the container:

```bash
git clone https://github.com/ekirton/poule.git
cd poule
```

The first time you run `poule`, it builds the Docker image and downloads the Coq search index automatically. No local Coq, Python, or opam installation is needed — everything runs inside the container.

## Usage

From any Coq project directory:

```bash
cd ~/Projects/my-coq-project
poule
```

This starts a shell inside the container with the Coq toolchain, Poule MCP server, and Claude Code all available. Run `claude` to start Claude Code:

```bash
[poule][main][~/Projects/my-coq-project]$ claude
```

You can also pass commands directly:

```bash
poule claude                     # Start Claude Code directly
poule coqc --version             # Run a command in the container
```

## What happens on first run

1. The Docker image is built (Coq 8.19.2, coq-lsp, Python 3.11, Claude Code)
2. A persistent home directory is created at `~/poule-home/`
3. The Coq search index is downloaded to `~/poule-home/data/`
4. Claude Code MCP settings are auto-configured

Subsequent runs skip all of these steps and start immediately.

## Persistent home directory

Poule stores all persistent state in `~/poule-home/`:

```
~/poule-home/
├── .claude/          # Claude Code settings, MCP config, auth
├── .ssh/             # SSH keys (copy yours here if needed)
├── .gitconfig        # Git configuration
├── .zsh_history      # Shell history
├── .zshrc            # Shell configuration
└── data/
    └── index.db      # Coq search index
```

Shell history, Claude Code settings, and authentication tokens persist across sessions. To set up git and SSH inside the container, copy your existing config:

```bash
cp ~/.gitconfig ~/poule-home/.gitconfig
cp -r ~/.ssh ~/poule-home/.ssh
```

## Adding the launcher to your PATH

Add the `bin/` directory to your PATH so you can run `poule` from anywhere:

```bash
# Add to ~/.zshrc or ~/.bashrc
export PATH="/path/to/poule/bin:$PATH"
```

## Updating Claude Code

Claude Code updates are applied automatically: when a new version is detected, the image rebuilds on exit. To update immediately:

```bash
poule --rebuild              # Update Claude CLI (uses cache)
poule --rebuild-all          # Full rebuild from scratch
```

## Updating the search index

To download a newer version of the search index:

```bash
rm ~/poule-home/data/index.db
poule   # Triggers automatic re-download
```

To also download the neural premise selection model:

```bash
poule uv run --project /app python -m poule.cli download-index --output ~/data/index.db --include-model
```
