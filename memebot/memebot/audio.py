import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg


class NoAudioTrack(Exception):
    """Video has no audio stream."""


class AudioExtractionFailed(Exception):
    """ffmpeg encountered an unexpected error."""


def extract_audio_track(video_bytes: bytes) -> bytes:
    """Return MP3 bytes for the audio track of *video_bytes*.

    Raises:
        NoAudioTrack: if the video has no audio stream.
        AudioExtractionFailed: on other ffmpeg errors.
    """
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory() as d:
        vp = Path(d) / "in.mp4"
        ap = Path(d) / "out.mp3"
        vp.write_bytes(video_bytes)
        proc = subprocess.run(
            [
                ffmpeg,
                "-i",
                str(vp),
                "-map",
                "0:a:0",
                "-vn",
                "-acodec",
                "libmp3lame",
                "-y",
                str(ap),
            ],
            capture_output=True,
            timeout=60,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode(errors="replace")
            if (
                "matches no streams" in stderr
                or "Failed to set value '0:a:0'" in stderr
            ):
                raise NoAudioTrack()
            raise AudioExtractionFailed(stderr[:500])
        return ap.read_bytes()
