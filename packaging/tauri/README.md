# HackKnow — Tauri desktop installer

Builds native installers for macOS, Windows, and Linux that wrap the FastAPI server in a desktop shell.

```bash
# 1) install rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 2) install Tauri CLI
cargo install create-tauri-app
cargo install tauri-cli --version "^2"

# 3) from this directory
cd packaging/tauri
cargo tauri build       # → .dmg / .msi / .deb / .AppImage
```

By default, the Tauri shell talks to a HackKnow API at `http://localhost:8787`. The bundled installer can spawn the API as a sidecar binary — see `tauri.conf.json` → `tauri.bundle.externalBin`.

For an installer that auto-starts the server, add a sidecar of `python -m server.api` and update `windows[0].url` to `http://localhost:8787`.
