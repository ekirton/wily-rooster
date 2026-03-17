# ============================================================================
# Stage 1: coq-base — Coq/Rocq toolchain (cached aggressively)
# Rebuilds only when Coq version changes.
# ============================================================================
FROM python:3.11-slim-bookworm AS coq-base

RUN apt-get update && apt-get install -y --no-install-recommends \
        bubblewrap \
        bzip2 \
        mercurial \
        darcs \
        gcc \
        libc6-dev \
        libgmp-dev \
        pkg-config \
        make \
        m4 \
        unzip \
        curl \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install opam (OCaml package manager)
RUN curl -fsSL https://raw.githubusercontent.com/ocaml/opam/master/shell/install.sh | \
        bash -s -- --no-backup

# Initialize opam without sandboxing (runs inside container already)
RUN opam init --disable-sandboxing --auto-setup --bare && \
    opam repository add --all default https://opam.ocaml.org

# Create OCaml switch and install Coq + coq-lsp
RUN opam switch create coq ocaml-base-compiler.4.14.2 && \
    eval $(opam env --switch=coq) && \
    opam repo add coq-released https://coq.inria.fr/opam/released --all-switches && \
    opam install -y coq.8.19.2 coq-lsp && \
    opam clean -a -c -s --logs

# Move opam to /opt so it's accessible to any user
RUN mv /root/.opam /opt/opam && chmod -R a+rX /opt/opam
ENV OPAMROOT=/opt/opam
ENV PATH="/opt/opam/coq/bin:${PATH}"

# ============================================================================
# Stage 2: app-deps — System packages + Python dependencies
# Rebuilds only when lockfiles change.
# ============================================================================
FROM coq-base AS app-deps

# Accept host user info as build args for proper file ownership
ARG HOST_UID=1000
ARG HOST_GID=1000
ARG HOST_USER=poule
ARG HOST_GROUP=poule

# Install Node.js and interactive tools
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends \
        nodejs \
        zsh \
        sudo \
        less \
        openssh-client \
        gnupg2 \
        gh \
        jq \
        wget \
        ripgrep \
        fd-find \
        bat \
        locales \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Configure UTF-8 locale
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# Create user matching host
RUN (getent group ${HOST_GID} >/dev/null 2>&1 || groupadd -g ${HOST_GID} ${HOST_GROUP}) && \
    useradd -m -u ${HOST_UID} -g ${HOST_GID} -s /bin/zsh ${HOST_USER}

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy only dependency manifests to cache the deps layer
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --group dev && chmod -R a+rX /app

# ============================================================================
# Stage 3: runtime — Application code + Claude Code
# Rebuilds on every source change (fast — just file copies).
# ============================================================================
FROM app-deps AS runtime

COPY src/ src/
COPY test/ test/
COPY examples/ examples/
COPY CLAUDE.md README.md ./
RUN chmod -R a+rX /app

# Cache-bust: changing this arg forces re-download of Claude Code
ARG CACHEBUST_CLAUDE=0
ARG CLAUDE_CODE_VERSION=latest

# Install Claude Code as user, then move to /opt
USER ${HOST_USER}
RUN curl -fsSL https://claude.ai/install.sh | bash -s ${CLAUDE_CODE_VERSION}

USER root
RUN mv /home/${HOST_USER}/.local/share/claude /opt/claude && \
    ln -sf "$(ls -d /opt/claude/versions/* | head -1)" /usr/local/bin/claude && \
    chown -R ${HOST_USER}:${HOST_GROUP} /opt/claude

USER ${HOST_USER}

# Minimal zshrc (overridden by persistent home mount at runtime)
RUN cat > ~/.zshrc << 'ZSHEOF'
setopt PROMPT_SUBST
_git_branch_colored() {
  local branch=$(git branch --show-current 2>/dev/null)
  if [ -n "$branch" ]; then
    if [ "$branch" = "main" ]; then
      echo "%F{red}[$branch]%f"
    else
      echo "%F{green}[$branch]%f"
    fi
  fi
}
PROMPT='%F{cyan}[poule]%f $(_git_branch_colored)%F{blue}[%~]%f$ '
HISTFILE=~/.zsh_history
HISTSIZE=10000
SAVEHIST=10000
export PATH="/opt/opam/coq/bin:$HOME/.local/bin:$PATH"
export UV_LINK_MODE="copy"
alias claude='claude --dangerously-skip-permissions'
ZSHEOF

# Record installed Claude Code version in image metadata
LABEL claude.code.version=${CLAUDE_CODE_VERSION}

VOLUME ["/data"]
ENV SHELL=/bin/zsh
CMD ["/bin/zsh"]
