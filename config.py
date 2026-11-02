"""Central settings for the AI Property Video Generator (lean version)."""

import os

# ---------- Output ----------
RESOLUTION = (1280, 720)
PREPARED_SIZE = (1344, 756)     # Photo size before the zoom crop
FPS = 24
BITRATE = "4000k"
ENCODE_PRESET = "veryfast"      # ultrafast, superfast, veryfast, faster, medium
ENCODE_THREADS = os.cpu_count() or 4
TEXT_OPACITY = 140

# ---------- Timing (seconds) ----------
TITLE_DURATION = 4.0
FEATURE_DURATION = 4.0
CTA_DURATION = 5.0
OVERVIEW_DURATION = 6.0
CROSSFADE = 0.5
MIN_TOTAL = 20.0
MAX_TOTAL = 40.0

# ---------- Camera and text motion ----------
ZOOM_START = 1.00
ZOOM_END = 1.06
SLIDE_UP_PIXELS = 36
SLIDE_UP_SECONDS = 0.7

# ---------- Content limits ----------
MAX_FEATURES = 5
MAX_KEY_FEATURES_INPUT = 6
MIN_IMAGES = 4
MAX_IMAGES = 8
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_LABEL_LENGTH = 40

# ---------- Voice-over ----------
NARRATION_DEFAULT = True
TTS_ENGINE = "edge"                 # "edge" (neural) or "gtts" (fallback)
EDGE_VOICE = "en-IN-NeerjaNeural"
EDGE_RATE = "-5%"
NARRATION_LANG = "en"               # gTTS fallback settings
NARRATION_TLD = "co.in"

# Spoken respellings. Key = written word, value = how the voice should say it.
PRONUNCIATIONS = {
    "Sunrise": "Sun rize",
    "BHK": "B H K",
    "24/7": "twenty four seven",
    "+91": "plus nine one",
    "sq.ft": "square feet",
    "Pvt": "private",
    "Ltd": "limited",
}

# ---------- Music ----------
DEFAULT_MUSIC_PATH = "assets/music/background.mp3"
MUSIC_VOLUME = 0.12                 # Quiet background level under the voice

# ---------- Brand colour and fonts ----------
ACCENT_RGB = (217, 119, 87)
DEFAULT_CTA = "Call us today to schedule a visit"
FONT_PATH = "assets/fonts/DejaVuSans.ttf"
FONT_BOLD_PATH = "assets/fonts/DejaVuSans-Bold.ttf"

# ---------- Paths ----------
DEFAULT_OUTPUT = "output/property_video.mp4"
LOG_PATH = "output/logs/run.log"
TEMP_DIR = "output/temp"

# Optional AI mode (key is read from the environment only)
AI_API_KEY_ENV = "PROPERTY_AI_API_KEY"