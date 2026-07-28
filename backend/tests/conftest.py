import sys
from pathlib import Path

# Tests import the backend modules the same way the app does (flat, no package),
# so the backend directory has to be importable.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _locate_ffmpeg() -> bool:
    """
    Make ffmpeg reachable for the tests that actually encode.

    Production gets it from static-ffmpeg. Locally that download is sometimes
    unavailable, so fall back to an imageio-ffmpeg wheel if one is installed.
    Everything except the encode tests runs fine without any of this.
    """
    from pydub import AudioSegment
    from pydub.utils import which

    if which("ffmpeg"):
        return True

    try:
        import static_ffmpeg

        static_ffmpeg.add_paths()
        if which("ffmpeg"):
            return True
    except Exception:
        pass

    try:
        import imageio_ffmpeg

        AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
        return True
    except Exception:
        return False


HAS_FFMPEG = _locate_ffmpeg()
