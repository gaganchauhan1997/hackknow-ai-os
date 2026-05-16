"""Video Editor Agent — Remotion + ffmpeg pipeline."""

from agents.base import BaseAgent


class VideoEditorAgent(BaseAgent):
    role_blurb = (
        "Video editor. Cuts, captions, transitions and renders via Remotion templates "
        "and ffmpeg. Always renders to MP4 H.264 by default."
    )
