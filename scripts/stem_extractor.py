#!/usr/bin/env python3
"""
Stem Extractor — Songwriter Toolkit
====================================
Separates audio into individual stems using Meta's Demucs.
Outputs: vocals, drums, bass, other (and optionally guitar/piano with htdemucs_6s).

Usage:
    python stem_extractor.py "track.mp3"
    python stem_extractor.py "track.mp3" --model htdemucs_ft --output ./stems
    python stem_extractor.py "track.mp3" --model htdemucs_6s --format flac
    python stem_extractor.py "track.mp3" --vocals-only

Requirements:
    pip install demucs torch torchaudio

Models:
    htdemucs       — Default hybrid transformer model. Fast, good quality.
    htdemucs_ft    — Fine-tuned version. Better quality, slower.
    htdemucs_6s    — 6-stem model: vocals, drums, bass, guitar, piano, other.
    mdx_extra      — MDX-Net architecture. Alternative quality profile.
"""

import argparse
import os
import sys
import time
import subprocess
import shutil
from pathlib import Path


MODELS = {
    "htdemucs": {
        "stems": ["vocals", "drums", "bass", "other"],
        "desc": "Hybrid Transformer (default, fast)",
    },
    "htdemucs_ft": {
        "stems": ["vocals", "drums", "bass", "other"],
        "desc": "Hybrid Transformer fine-tuned (better quality, slower)",
    },
    "htdemucs_6s": {
        "stems": ["vocals", "drums", "bass", "guitar", "piano", "other"],
        "desc": "6-stem model (adds guitar + piano separation)",
    },
    "mdx_extra": {
        "stems": ["vocals", "drums", "bass", "other"],
        "desc": "MDX-Net architecture (alternative quality profile)",
    },
}


def check_demucs():
    """Check if demucs is installed."""
    try:
        import demucs
        return True
    except ImportError:
        return False


def check_ffmpeg():
    """Check if ffmpeg is available."""
    return shutil.which("ffmpeg") is not None


def extract_stems(
    audio_path: str,
    model: str = "htdemucs",
    output_dir: str = None,
    output_format: str = "wav",
    vocals_only: bool = False,
    mp3_bitrate: int = 320,
    two_stems: str = None,
    shifts: int = 1,
    overlap: float = 0.25,
    device: str = None,
):
    """
    Extract stems from an audio file using Demucs.

    Args:
        audio_path: Path to input audio file
        model: Demucs model name
        output_dir: Output directory (default: same dir as input / stems)
        output_format: Output format (wav, mp3, flac)
        vocals_only: If True, only extract vocals stem
        mp3_bitrate: MP3 bitrate if format is mp3
        two_stems: If set, separate into this stem + rest (e.g., 'vocals')
        shifts: Number of random shifts for prediction (more = better but slower)
        overlap: Overlap between prediction windows
        device: Force device (cpu, cuda)
    """
    audio_path = Path(audio_path).resolve()

    if not audio_path.exists():
        print(f"  ❌ File not found: {audio_path}")
        sys.exit(1)

    if model not in MODELS:
        print(f"  ❌ Unknown model: {model}")
        print(f"  Available: {', '.join(MODELS.keys())}")
        sys.exit(1)

    # Set output directory
    if output_dir is None:
        output_dir = audio_path.parent / "stems"
    output_dir = Path(output_dir)

    track_name = audio_path.stem

    print(f"\n🎵 STEM EXTRACTOR")
    print(f"{'=' * 60}")
    print(f"  Input:    {audio_path.name}")
    print(f"  Model:    {model} ({MODELS[model]['desc']})")
    print(f"  Stems:    {', '.join(MODELS[model]['stems'])}")
    print(f"  Format:   {output_format}")
    print(f"  Output:   {output_dir}")
    if vocals_only or two_stems:
        stem = two_stems or "vocals"
        print(f"  Mode:     Two-stem ({stem} + no_{stem})")
    print(f"  Shifts:   {shifts}")
    print(f"  Overlap:  {overlap}")
    print()

    # Build demucs command
    cmd = [
        sys.executable, "-m", "demucs",
        "--name", model,
        "--out", str(output_dir),
    ]

    if output_format == "mp3":
        cmd.extend(["--mp3", "--mp3-bitrate", str(mp3_bitrate)])
    elif output_format == "flac":
        cmd.append("--flac")
    # wav is default

    if vocals_only:
        cmd.extend(["--two-stems", "vocals"])
    elif two_stems:
        cmd.extend(["--two-stems", two_stems])

    if shifts > 1:
        cmd.extend(["--shifts", str(shifts)])

    if overlap != 0.25:
        cmd.extend(["--overlap", str(overlap)])

    if device:
        cmd.extend(["--device", device])

    cmd.append(str(audio_path))

    print(f"  Running Demucs...")
    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(audio_path.parent),
        )

        if result.returncode != 0:
            print(f"  ❌ Demucs failed:")
            print(f"  {result.stderr}")
            sys.exit(1)

    except FileNotFoundError:
        print(f"  ❌ Could not run Demucs. Is it installed?")
        print(f"  Run: pip install demucs torch torchaudio")
        sys.exit(1)

    elapsed = time.time() - start_time

    # Find output files
    stem_dir = output_dir / model / track_name

    if not stem_dir.exists():
        print(f"  ❌ Expected output directory not found: {stem_dir}")
        print(f"  Demucs stdout: {result.stdout}")
        sys.exit(1)

    # Collect results
    ext = output_format if output_format != "wav" else "wav"
    stems_found = []

    for stem_file in sorted(stem_dir.iterdir()):
        if stem_file.is_file() and stem_file.suffix in [".wav", ".mp3", ".flac"]:
            size_mb = stem_file.stat().st_size / (1024 * 1024)
            stems_found.append({
                "name": stem_file.stem,
                "path": str(stem_file),
                "size_mb": size_mb,
            })

    print(f"\n{'=' * 60}")
    print(f"✅ STEMS EXTRACTED ({elapsed:.1f}s)")
    print(f"{'=' * 60}")

    for stem in stems_found:
        print(f"  🎚️  {stem['name']:12s}  {stem['size_mb']:6.1f} MB  → {stem['path']}")

    print(f"\n  📁 Output: {stem_dir}")
    print(f"  ⏱️  Time:   {elapsed:.1f}s")
    print()

    return {
        "stems": stems_found,
        "output_dir": str(stem_dir),
        "model": model,
        "elapsed": elapsed,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Extract stems from audio using Meta's Demucs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Models:
  htdemucs      Hybrid Transformer (default, fast)
  htdemucs_ft   Fine-tuned (better quality, slower)
  htdemucs_6s   6-stem: vocals, drums, bass, guitar, piano, other
  mdx_extra     MDX-Net (alternative quality)

Examples:
  %(prog)s "track.mp3"
  %(prog)s "track.mp3" --model htdemucs_ft --output ./stems
  %(prog)s "track.mp3" --model htdemucs_6s --format flac
  %(prog)s "track.mp3" --vocals-only
  %(prog)s "track.mp3" --two-stems drums
  %(prog)s "track.mp3" --shifts 5 --model htdemucs_ft  (highest quality)
        """,
    )

    parser.add_argument("audio", help="Path to audio file")
    parser.add_argument(
        "--model", "-m",
        default="htdemucs",
        choices=list(MODELS.keys()),
        help="Demucs model (default: htdemucs)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory (default: ./stems)",
    )
    parser.add_argument(
        "--format", "-f",
        default="wav",
        choices=["wav", "mp3", "flac"],
        help="Output format (default: wav)",
    )
    parser.add_argument(
        "--vocals-only",
        action="store_true",
        help="Only extract vocals + no_vocals",
    )
    parser.add_argument(
        "--two-stems",
        default=None,
        help="Separate into specified stem + rest (e.g., 'drums', 'bass')",
    )
    parser.add_argument(
        "--mp3-bitrate",
        type=int,
        default=320,
        help="MP3 bitrate if format is mp3 (default: 320)",
    )
    parser.add_argument(
        "--shifts",
        type=int,
        default=1,
        help="Random shifts for better quality (1=fast, 5=best, default: 1)",
    )
    parser.add_argument(
        "--overlap",
        type=float,
        default=0.25,
        help="Overlap between windows (default: 0.25)",
    )
    parser.add_argument(
        "--device",
        default=None,
        choices=["cpu", "cuda"],
        help="Force device (default: auto-detect)",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available models and exit",
    )

    args = parser.parse_args()

    if args.list_models:
        print("\n🎵 Available Demucs Models")
        print("=" * 60)
        for name, info in MODELS.items():
            print(f"  {name:16s} {info['desc']}")
            print(f"  {'':16s} Stems: {', '.join(info['stems'])}")
            print()
        sys.exit(0)

    # Pre-flight checks
    if not check_demucs():
        print("❌ Demucs not installed.")
        print("   Run: pip install demucs torch torchaudio")
        sys.exit(1)

    extract_stems(
        audio_path=args.audio,
        model=args.model,
        output_dir=args.output,
        output_format=args.format,
        vocals_only=args.vocals_only,
        mp3_bitrate=args.mp3_bitrate,
        two_stems=args.two_stems,
        shifts=args.shifts,
        overlap=args.overlap,
        device=args.device,
    )


if __name__ == "__main__":
    main()
