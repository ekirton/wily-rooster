# ============================================================================
# Stage 1: coq-base — Coq/Rocq toolchain (cached aggressively)
# Rebuilds only when Coq version changes.
# ============================================================================
FROM python:3.11-slim-bookworm AS coq-base

RUN apt-get update && apt-get install -y --no-install-recommends \
        bubblewrap \
        mercurial \
        darcs \
        gcc \
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
# --bare skips default switch but also skips the default repo, so add it back
RUN opam init --disable-sandboxing --auto-setup --bare && \
    opam repository add --all default https://opam.ocaml.org

# Create OCaml switch and install Coq + coq-lsp
RUN opam switch create coq ocaml-base-compiler.4.14.2 && \
    eval $(opam env --switch=coq) && \
    opam repo add coq-released https://coq.inria.fr/opam/released --all-switches && \
    opam install -y coq.8.19.2 coq-lsp && \
    opam clean -a -c -s --logs

# ============================================================================
# Stage 2: app-deps — Python + Node.js dependencies
# Rebuilds only when lockfiles change.
# ============================================================================
FROM coq-base AS app-deps

# Install Node.js 22.x
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Claude Code globally
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app

# Copy only dependency manifests to cache the deps layer
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --group dev

# ============================================================================
# Stage 3: runtime — Application code
# Rebuilds on every source change (fast — just file copies).
# ============================================================================
FROM app-deps AS runtime

COPY src/ src/
COPY test/ test/
COPY examples/ examples/
COPY CLAUDE.md README.md ./

# Make Coq binaries available on PATH
ENV PATH="/root/.opam/coq/bin:${PATH}"
RUN echo 'eval $(opam env --switch=coq)' >> /root/.bashrc

VOLUME ["/data"]

ENTRYPOINT ["uv", "run", "python", "-m", "poule.server"]
CMD ["--db", "/data/index.db"]
