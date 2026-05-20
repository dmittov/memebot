import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
import pytest

from memebot.audio import AudioExtractionFailed, NoAudioTrack, extract_audio_track


class TestExtractAudioTrack:
    def test_returns_mp3_bytes_when_video_has_audio(self):
        """frage.mp4 has audio — expect non-empty MP3 output."""
        video = Path("tests/img/frage.mp4").read_bytes()
        audio = extract_audio_track(video)
        assert len(audio) > 0
        # MP3 magic: "ID3" tag header or sync-word 0xFF 0xFx
        assert audio[:3] == b"ID3" or (audio[0] == 0xFF and (audio[1] & 0xE0) == 0xE0)

    def test_raises_no_audio_track_when_video_is_silent(self):
        """Video without an audio stream raises NoAudioTrack."""
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "silent.mp4"
            subprocess.run(
                [
                    ffmpeg,
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=64x64:d=1",
                    "-an",
                    "-y",
                    str(out),
                ],
                capture_output=True,
                check=True,
            )
            video = out.read_bytes()
        with pytest.raises(NoAudioTrack):
            extract_audio_track(video)

    def test_raises_audio_extraction_failed_on_corrupted_input(self):
        """Garbage bytes are not a valid video — ffmpeg fails."""
        with pytest.raises(AudioExtractionFailed):
            extract_audio_track(b"this is not a video file")
