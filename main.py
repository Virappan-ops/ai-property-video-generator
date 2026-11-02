"""Command-Line Interface entry point for the AI Property Video Generator."""

import argparse
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import List, Optional
import config
from src.errors import PropertyVideoError
from src.image_checker import check_and_prepare_images
from src.input_loader import load_interactive_input, load_json_input
from src.logger import log_exception, log_step
from src.narrator import generate_narration
from src.scene_planner import plan_scenes
from src.script_generator import generate_script_package, save_script_file
from src.video_builder import build_and_export_video, verify_ffmpeg_available


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser matching Section 7.2."""
    parser = argparse.ArgumentParser(
        prog="ai-property-video-generator",
        description="Turn property details and 4-8 photos into a narrated 1280x720 promotional MP4 video.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--input", type=str, help="Path to the property JSON file")
    mode_group.add_argument(
        "--interactive",
        action="store_true",
        help="Ask for details in the terminal instead of a JSON file",
    )

    parser.add_argument(
        "--image-dir",
        type=str,
        default=None,
        help="Folder of images (used with --interactive)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=config.DEFAULT_OUTPUT,
        help=f"Output MP4 path (default: {config.DEFAULT_OUTPUT})",
    )

    narr_group = parser.add_mutually_exclusive_group()
    narr_group.add_argument(
        "--narrate",
        action="store_true",
        help="Force narration on (this is already the default)",
    )
    narr_group.add_argument(
        "--no-narrate",
        action="store_true",
        help="Turn narration off, producing a silent video",
    )

    parser.add_argument(
        "--music",
        type=str,
        default=None,
        help="Background music file; overrides music_path in JSON",
    )
    parser.add_argument(
        "--no-music",
        action="store_true",
        help="Disable background music even if music_path is set",
    )
    parser.add_argument(
        "--use-ai",
        action="store_true",
        help="OPTIONAL. Use an AI model for the narration script",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Open the generated MP4 with the system default player after export",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed progress and keep temporary files",
    )
    return parser


def _open_preview(video_path: Path) -> None:
    """Open the exported video with the OS default media player."""
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(str(video_path))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.run(["open", str(video_path)], check=False)
        else:
            subprocess.run(["xdg-open", str(video_path)], check=False)
    except Exception as exc:
        log_step(f"Note: Could not automatically open preview player ({exc}).")


def run_cli(argv: Optional[List[str]] = None) -> int:
    """Execute the complete pipeline and return the process exit code (0, 1, 2, or 3)."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.input and not args.interactive:
        parser.print_help()
        return 1

    try:
        verify_ffmpeg_available()

        # 1. Load & Validate Input
        if args.interactive:
            img_dir = Path(args.image_dir) if args.image_dir else None
            prop_data = load_interactive_input(image_dir_override=img_dir)
            base_dir = img_dir.parent if img_dir else Path(".")
        else:
            input_path = Path(args.input)
            prop_data = load_json_input(input_path)
            base_dir = input_path.parent
        log_step("Validating input... OK")

        # Apply CLI overrides for narration and music
        if args.no_narrate:
            prop_data.narration_enabled = False
        elif args.narrate:
            prop_data.narration_enabled = True

        if args.no_music:
            prop_data.music_path = None
        elif args.music:
            prop_data.music_path = Path(args.music)

        # 2. Check and Prepare Images
        temp_dir = Path(config.TEMP_DIR)
        prepared_images, skipped_count = check_and_prepare_images(
            prop_data.images,
            temp_dir=temp_dir,
            base_dir=base_dir,
        )
        log_step(f"Checking images ({len(prepared_images)} found, {skipped_count} skipped)... OK")

        # 3. Build Script & Scene Texts
        script_pkg = generate_script_package(prop_data, use_ai=args.use_ai)
        log_step("Building script... OK")

        # 4. Generate Narration (if enabled)
        narration_path: Optional[Path] = None
        narration_duration: Optional[float] = None
        if prop_data.narration_enabled:
            narration_path, narr_dur, updated_script = generate_narration(
                script_pkg.narration_script,
                data=prop_data,
                temp_dir=temp_dir,
            )
            script_pkg.narration_script = updated_script
            if narration_path is not None:
                narration_duration = narr_dur
                log_step(f"Generating narration (gTTS)... OK ({narr_dur:.1f} seconds of speech)")

        output_path = Path(args.output)
        save_script_file(script_pkg, output_path)

        # 5. Plan Scenes
        plan = plan_scenes(
            data=prop_data,
            prepared_images=prepared_images,
            narration_duration=narration_duration,
        )
        log_step(f"Planning scenes ({len(plan.scenes)} scenes, {plan.total_duration:.1f} seconds)... OK")

        # 6. Render & Export MP4
        build_and_export_video(
            plan=plan,
            output_path=output_path,
            narration_path=narration_path,
            music_path=prop_data.music_path,
            temp_dir=temp_dir,
            keep_temp=args.verbose,
        )

        if args.preview:
            _open_preview(output_path)

        return 0

    except PropertyVideoError as exc:
        print(f"Error: {exc.message}")
        print(f"Suggestion: {exc.suggestion}")
        return exc.exit_code
    except Exception as exc:
        log_exception(exc)
        print("Unexpected error. Details are in output/logs/run.log.")
        return 2


if __name__ == "__main__":
    sys.exit(run_cli())