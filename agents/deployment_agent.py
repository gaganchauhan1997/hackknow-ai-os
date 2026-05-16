"""Deployment Agent — packages and ships HackKnow projects (Docker, Vercel, Tauri, Capacitor)."""

from agents.base import BaseAgent


class DeploymentAgent(BaseAgent):
    role_blurb = (
        "Deployment specialist. Writes Dockerfiles, docker-compose, GitHub Actions, "
        "Tauri configs, Capacitor configs, and shell scripts. Knows Vercel, Railway, "
        "Fly.io, Render, GCP, AWS, Kubernetes."
    )
