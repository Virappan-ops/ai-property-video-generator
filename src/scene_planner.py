"""Plans scene lengths from the voice lines so each line plays while its text is on screen."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import config
from src.input_loader import PropertyData
from src.logger import log_warning
from src.script_generator import SceneText, build_scene_texts, image_index_for_scene

SpeechSegment = Tuple[Path, float]  # (mp3 path, duration in seconds)
SPEECH_LEAD = config.CROSSFADE      # Voice starts after the scene text has faded in
SPEECH_TAIL_PAD = 0.8               # Silence after the voice line before the scene ends
FEATURE_MIN_FAST = 3.0              # Shorter feature scenes, used only if the video would be too long


@dataclass
class PlannedScene:
    """One scene: timing, photo, on-screen text, and its voice-over clip."""

    scene_index: int
    scene_type: str
    duration: float
    start: float  # Position on the final timeline (includes the crossfade overlap)
    image_path: Path
    scene_text: SceneText
    speech_path: Optional[Path] = None
    speech_seconds: float = 0.0


@dataclass
class ScenePlan:
    """Complete timing and asset plan for the video."""

    scenes: List[PlannedScene]
    total_duration: float
    crossfade: float = config.CROSSFADE


def compute_real_duration(durations: List[float], crossfade: float = config.CROSSFADE) -> float:
    """Return the real output length after subtracting crossfade overlaps."""
    if not durations:
        return 0.0
    return round(sum(durations) - crossfade * (len(durations) - 1), 3)


def _assign_images(scene_count: int, images: List[Path]) -> List[Path]:
    """Map photos to scenes (title = first photo, closing = last photo, middle in order)."""
    return [images[image_index_for_scene(i, scene_count, len(images))] for i in range(scene_count)]


def _min_duration(scene_type: str, has_features: bool, feature_min: float) -> float:
    """Return the shortest allowed length for a scene type."""
    if scene_type == "title":
        return config.TITLE_DURATION
    if scene_type == "cta":
        return config.CTA_DURATION
    if scene_type == "overview" and not has_features:
        return config.OVERVIEW_DURATION
    return feature_min


def _durations(
    scenes: List[SceneText],
    speech: Optional[List[SpeechSegment]],
    feature_min: float,
) -> List[float]:
    """Each scene is at least its minimum length, and long enough for its voice line."""
    has_features = any(sc.scene_type == "feature" for sc in scenes)
    result: List[float] = []
    for i, sc in enumerate(scenes):
        length = _min_duration(sc.scene_type, has_features, feature_min)
        if speech is not None:
            length = max(length, speech[i][1] + SPEECH_LEAD + SPEECH_TAIL_PAD)
        result.append(round(length, 2))
    return result


def plan_scenes(
    data: PropertyData,
    prepared_images: List[Path],
    speech: Optional[List[SpeechSegment]] = None,
) -> ScenePlan:
    """Plan scenes so each voice line plays during its scene and the video stays within 20 to 40 seconds."""
    scenes = build_scene_texts(data, max_features=config.MAX_FEATURES)

    if speech is not None and len(speech) != len(scenes):
        log_warning("Warning: Voice-over lines do not match the scenes. Exporting without narration.")
        speech = None

    durations = _durations(scenes, speech, config.FEATURE_DURATION)
    if compute_real_duration(durations) > config.MAX_TOTAL:
        durations = _durations(scenes, speech, FEATURE_MIN_FAST)

    total = compute_real_duration(durations)
    if total > config.MAX_TOTAL:
        log_warning(
            f"Warning: Video is {total:.1f} seconds, longer than {config.MAX_TOTAL:.0f}. "
            "Use fewer key features or shorter voice lines."
        )
    if total < config.MIN_TOTAL:
        durations[-1] = round(durations[-1] + (config.MIN_TOTAL - total), 2)
        total = compute_real_duration(durations)

    images = _assign_images(len(scenes), prepared_images)

    planned: List[PlannedScene] = []
    start = 0.0
    for i, sc in enumerate(scenes):
        seg = speech[i] if speech is not None else None
        planned.append(
            PlannedScene(
                scene_index=i + 1,
                scene_type=sc.scene_type,
                duration=durations[i],
                start=round(start, 3),
                image_path=images[i],
                scene_text=sc,
                speech_path=seg[0] if seg else None,
                speech_seconds=seg[1] if seg else 0.0,
            )
        )
        start += durations[i] - config.CROSSFADE

    return ScenePlan(scenes=planned, total_duration=total)