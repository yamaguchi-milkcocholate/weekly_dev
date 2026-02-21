"""生成動画からフレームを1秒間隔で抽出するスクリプト.

Usage:
    uv run python poc/video_ai/extract_frames.py [--ais veo,kling,luma,runway]
"""

import argparse
import logging
import subprocess
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
ALL_AIS = ["veo", "kling", "luma", "runway"]


def extract_frames(video_path: Path, output_dir: Path) -> list[Path]:
    """FFmpegで動画から1秒間隔でフレームを抽出する."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 既存フレームをクリア
    for f in output_dir.glob("frame_*.png"):
        f.unlink()

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", "fps=1",
        str(output_dir / "frame_%03d.png"),
    ]
    logger.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr}")

    frames = sorted(output_dir.glob("frame_*.png"))
    logger.info("Extracted %d frames -> %s", len(frames), output_dir)
    return frames


def main(ais: list[str]) -> None:
    for ai in ais:
        video_dir = BASE_DIR / "generated" / ai
        video_path = video_dir / "output.mp4"
        if not video_path.exists():
            logger.warning("%s: video not found at %s (skipping)", ai, video_path)
            continue

        output_dir = BASE_DIR / "frames" / ai
        frames = extract_frames(video_path, output_dir)
        logger.info("%s: %d frames extracted", ai, len(frames))

    logger.info("Frame extraction complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="動画からフレーム抽出")
    parser.add_argument("--ais", default=",".join(ALL_AIS), help="対象AI (カンマ区切り)")
    args = parser.parse_args()
    main([a.strip() for a in args.ais.split(",")])
