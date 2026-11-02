# AI Models, APIs, and Libraries Used

## 1. Python Libraries (Pinned in `requirements.txt`)
| Library | Version | Purpose |
|---|---|---|
| `Pillow` | `10.4.0` | Image validation, `Image.LANCZOS` cover-fit resizing (1344x756), per-frame zoom cropping (1280x720), and transparent RGBA text overlays |
| `moviepy` | `1.0.3` | Video clip assembly, layer compositing, 0.5s fade/crossfade transitions, audio mixing, and H.264/AAC MP4 export |
| `numpy` | `1.26.4` | Frame buffer array operations required by `moviepy==1.0.3` |
| `imageio` | `2.31.6` | Frame I/O backend for MoviePy |
| `imageio-ffmpeg` | `0.4.9` | Bundled FFmpeg binary so no separate system FFmpeg installation is required |
| `gTTS` | `2.5.1` | Google Text-to-Speech client used to synthesize default spoken narration (`lang="en"`, `tld="co.in"`) |
| `pytest` | `8.2.2` | Automated unit and integration test runner |

## 2. External Services & AI Models
1. **Default Mode (Template Logic + Google Text-to-Speech via `gTTS`):**
   - **Script & Captions:** Generated deterministically using template rules (`src/script_generator.py`). Zero facts are invented.
   - **Spoken Narration:** Uses Google Text-to-Speech (`gTTS==2.5.1`) to convert the narration script into `output/temp/narration.mp3`. It receives only the plain narration text string—never images, local paths, or personal data. If offline, the tool prints a clear warning and exports a silent video without crashing.
2. **Optional AI Script Mode (`--use-ai`):**
   - When explicitly invoked with `--use-ai` and an environment variable `PROPERTY_AI_API_KEY`, `src/script_generator.py` sends only the supplied property JSON text fields to Google Gemini (`gemini-2.5-flash`) with strict instructions to write a 2–3 sentence narration using only the provided facts.
   - Every AI response is verified by `src/fact_checker.py` (checking all numbers, exact spelling of property name/location/type, character length, and blocked phrases like `"guaranteed returns"` or `"luxury"`). If fact-checking fails or no key is set, the application automatically falls back to template mode.

## 3. Security & Data Privacy Confirmation
- **No API keys, passwords, or secrets** are stored anywhere in the code, `config.py`, or git repository.
- All sample inputs (`input/property.json` and `input/images/img1.jpg`..`img5.jpg`) are 100% synthetic placeholder data.