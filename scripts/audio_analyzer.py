#!/usr/bin/env python3
"""
Audio Analyzer — Songwriter Skill Support Tool
Analyzes audio files for BPM, key, energy, sections, and mood.
Outputs structured data to inform lyric writing, storyboarding, and Veo3 prompts.

Usage:
    python audio_analyzer.py <audio_file> [--output json|text|full] [--plot]

Requirements:
    pip install librosa numpy scipy soundfile matplotlib
"""

import argparse
import json
import sys
import os
from pathlib import Path
from datetime import timedelta

try:
    import librosa
    import numpy as np
    from scipy import stats
except ImportError:
    print("ERROR: Missing dependencies. Install with:")
    print("  pip install librosa numpy scipy soundfile")
    sys.exit(1)


# ─── Key Detection ───────────────────────────────────────────────────────────

PITCH_CLASSES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Krumhansl-Kessler key profiles
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def detect_key(y, sr):
    """Detect musical key using chroma features + Krumhansl-Kessler profiles."""
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = np.mean(chroma, axis=1)

    major_corrs = []
    minor_corrs = []

    for i in range(12):
        rotated = np.roll(chroma_mean, -i)
        major_corr = np.corrcoef(rotated, MAJOR_PROFILE)[0, 1]
        minor_corr = np.corrcoef(rotated, MINOR_PROFILE)[0, 1]
        major_corrs.append(major_corr)
        minor_corrs.append(minor_corr)

    best_major_idx = np.argmax(major_corrs)
    best_minor_idx = np.argmax(minor_corrs)

    if major_corrs[best_major_idx] >= minor_corrs[best_minor_idx]:
        return f"{PITCH_CLASSES[best_major_idx]} major", major_corrs[best_major_idx]
    else:
        return f"{PITCH_CLASSES[best_minor_idx]} minor", minor_corrs[best_minor_idx]


# ─── BPM Detection ──────────────────────────────────────────────────────────

def detect_bpm(y, sr):
    """Detect BPM with confidence score."""
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)

    # Handle both scalar and array returns from different librosa versions
    if hasattr(tempo, '__len__'):
        tempo = float(tempo[0])
    else:
        tempo = float(tempo)

    # Confidence from autocorrelation
    ac = librosa.autocorrelate(onset_env, max_size=len(onset_env))
    ac = ac / ac[0]  # normalize

    # Find the peak near the detected tempo
    bpm_lag = int(60.0 * sr / (tempo * 512))  # hop_length default is 512
    search_range = max(1, bpm_lag // 10)
    start = max(0, bpm_lag - search_range)
    end = min(len(ac), bpm_lag + search_range)
    confidence = float(np.max(ac[start:end])) if start < end else 0.5

    return round(tempo), confidence, beat_frames


# ─── Energy Analysis ─────────────────────────────────────────────────────────

def analyze_energy(y, sr, n_segments=16):
    """Break audio into segments and measure energy profile."""
    segment_length = len(y) // n_segments
    energies = []

    for i in range(n_segments):
        start = i * segment_length
        end = start + segment_length
        segment = y[start:end]
        rms = float(np.sqrt(np.mean(segment ** 2)))
        energies.append(rms)

    # Normalize to 0-1
    max_e = max(energies) if max(energies) > 0 else 1
    energies_norm = [round(e / max_e, 3) for e in energies]

    # Find peaks and drops
    energy_arr = np.array(energies_norm)
    mean_e = np.mean(energy_arr)

    peaks = [i for i, e in enumerate(energies_norm) if e > mean_e + 0.15]
    drops = [i for i, e in enumerate(energies_norm) if e < mean_e - 0.15]

    return {
        "segments": energies_norm,
        "peak_segments": peaks,
        "drop_segments": drops,
        "overall_rms": round(float(np.sqrt(np.mean(y ** 2))), 4),
        "dynamic_range": round(float(max(energies_norm) - min(energies_norm)), 3),
    }


# ─── Section Detection ──────────────────────────────────────────────────────

def _compute_novelty(features, sr):
    """Compute novelty curve from feature matrix, compatible with all librosa versions."""
    # Try librosa.segment.novelty first (older versions)
    try:
        novelty = librosa.segment.novelty(features, k=64)
        return novelty
    except AttributeError:
        pass

    # Fallback: checkerboard kernel novelty from feature self-distance
    from scipy.ndimage import gaussian_filter1d

    # Compute frame-to-frame cosine distance
    n_frames = features.shape[1]
    novelty = np.zeros(n_frames)

    # Use a checkerboard kernel approach on the self-similarity
    kernel_size = 64  # ~3 seconds at default hop
    half_k = kernel_size // 2

    # Compute pairwise distances between consecutive feature blocks
    for i in range(half_k, n_frames - half_k):
        block_before = features[:, i - half_k:i]
        block_after = features[:, i:i + half_k]

        # Mean cosine distance between the two blocks
        mean_before = np.mean(block_before, axis=1)
        mean_after = np.mean(block_after, axis=1)

        # Euclidean distance between block centroids
        dist = np.linalg.norm(mean_after - mean_before)
        novelty[i] = dist

    # Smooth to remove micro-fluctuations
    novelty = gaussian_filter1d(novelty, sigma=8)

    # Normalize
    if np.max(novelty) > 0:
        novelty /= np.max(novelty)

    return novelty


def detect_sections(y, sr, duration):
    """Detect structural sections using spectral analysis."""
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

    # Combine features
    features = np.vstack([
        librosa.util.normalize(mfcc, axis=1),
        librosa.util.normalize(chroma, axis=1),
    ])

    # Structural segmentation via novelty
    novelty = _compute_novelty(features, sr).astype(np.float64)

    # Adaptive threshold: only keep peaks above the 75th percentile
    threshold = float(np.percentile(novelty[novelty > 0], 75)) if np.any(novelty > 0) else 0.3

    # Minimum gap between sections: ~10 seconds in frames
    hop_length = 512
    min_section_frames = int(10 * sr / hop_length)

    # Find segment boundaries with aggressive filtering
    peaks = librosa.util.peak_pick(
        novelty,
        pre_max=int(min_section_frames // 2),
        post_max=int(min_section_frames // 2),
        pre_avg=int(min_section_frames),
        post_avg=int(min_section_frames),
        delta=float(threshold * 0.5),
        wait=int(min_section_frames)
    )

    # Convert frame indices to time
    times = librosa.frames_to_time(peaks, sr=sr)

    # Filter out boundaries too close to start/end (< 3s)
    times = [t for t in times if 3.0 < t < duration - 3.0]

    # Cap at reasonable number of sections (max ~15 for a 5-min track)
    if len(times) > 15:
        # Keep only the strongest peaks
        peak_strengths = [(t, novelty[librosa.time_to_frames(t, sr=sr)]) for t in times]
        peak_strengths.sort(key=lambda x: x[1], reverse=True)
        times = sorted([t for t, _ in peak_strengths[:15]])

    # Build section list
    sections = []
    boundaries = [0.0] + list(times) + [duration]

    for i in range(len(boundaries) - 1):
        start_t = boundaries[i]
        end_t = boundaries[i + 1]
        length = end_t - start_t

        # Classify section type by position and length
        if i == 0 and length < 15:
            label = "intro"
        elif i == len(boundaries) - 2 and length < 15:
            label = "outro"
        elif length < 8:
            label = "transition"
        elif length < 20:
            label = "hook/chorus"
        else:
            label = "verse"

        sections.append({
            "index": i + 1,
            "label": label,
            "start": round(start_t, 1),
            "end": round(end_t, 1),
            "duration": round(length, 1),
            "timestamp": str(timedelta(seconds=int(start_t))),
        })

    return sections


# ─── Mood Classification ────────────────────────────────────────────────────

def classify_mood(y, sr, key_name, bpm, energy_data):
    """Estimate mood from audio features."""
    spectral_centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    spectral_rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr)))
    zcr = float(np.mean(librosa.feature.zero_crossing_rate(y)))

    is_minor = "minor" in key_name
    is_high_energy = energy_data["overall_rms"] > 0.05
    is_bright = spectral_centroid > 2000
    is_fast = bpm > 120

    # Mood matrix
    moods = []

    if is_minor and is_high_energy:
        moods.append("dark")
        moods.append("aggressive")
    elif is_minor and not is_high_energy:
        moods.append("melancholic")
        moods.append("atmospheric")
    elif not is_minor and is_high_energy:
        moods.append("energetic")
        moods.append("euphoric")
    else:
        moods.append("chill")
        moods.append("warm")

    if is_fast and is_high_energy:
        moods.append("intense")
    if is_bright:
        moods.append("vibrant")
    if zcr > 0.1:
        moods.append("textured")
    if energy_data["dynamic_range"] > 0.5:
        moods.append("dynamic")

    return {
        "moods": moods[:4],
        "spectral_centroid_hz": round(spectral_centroid),
        "spectral_rolloff_hz": round(spectral_rolloff),
        "zero_crossing_rate": round(zcr, 4),
        "brightness": "bright" if is_bright else "warm",
        "tonality": "minor" if is_minor else "major",
    }


# ─── Frequency Spectrum ─────────────────────────────────────────────────────

def analyze_spectrum(y, sr):
    """Analyze frequency band distribution."""
    S = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)

    # Define frequency bands
    bands = {
        "sub_bass": (20, 60),
        "bass": (60, 250),
        "low_mid": (250, 500),
        "mid": (500, 2000),
        "upper_mid": (2000, 4000),
        "presence": (4000, 6000),
        "brilliance": (6000, 20000),
    }

    band_energies = {}
    total = float(np.sum(S ** 2))

    for name, (low, high) in bands.items():
        mask = (freqs >= low) & (freqs < high)
        if np.any(mask):
            band_energy = float(np.sum(S[mask] ** 2))
            band_energies[name] = round(band_energy / total * 100, 1) if total > 0 else 0
        else:
            band_energies[name] = 0

    # Determine dominant character
    dominant = max(band_energies, key=band_energies.get)

    return {
        "bands_percent": band_energies,
        "dominant_band": dominant,
        "character": get_spectrum_character(dominant),
    }


def get_spectrum_character(dominant):
    """Map dominant frequency band to sonic character."""
    chars = {
        "sub_bass": "808-heavy, chest-rattling low end",
        "bass": "punchy, warm bass foundation",
        "low_mid": "full, muddy-risk territory — may need EQ",
        "mid": "vocal-forward, clear",
        "upper_mid": "cutting, aggressive presence",
        "presence": "airy, detailed, crisp snares",
        "brilliance": "sparkly, hi-hat forward, bright",
    }
    return chars.get(dominant, "balanced")


# ─── Suno Style Prompt Generator ────────────────────────────────────────────

def generate_suno_prompt(analysis):
    """Generate a Suno-ready style prompt from audio analysis."""
    key = analysis["key"]["detected"]
    bpm = analysis["bpm"]["tempo"]
    moods = analysis["mood"]["moods"]
    brightness = analysis["mood"]["brightness"]
    dominant = analysis["spectrum"]["dominant_band"]

    # Genre hints from analysis
    genre_hints = []
    if bpm >= 130 and bpm <= 150 and "dark" in moods:
        genre_hints.append("dark trap")
    elif bpm >= 135 and bpm <= 145:
        genre_hints.append("UK grime")
    elif bpm >= 140 and bpm <= 160 and "aggressive" in moods:
        genre_hints.append("drill")
    elif bpm >= 120 and bpm <= 135:
        genre_hints.append("trap")
    elif bpm >= 85 and bpm <= 100:
        genre_hints.append("boom bap")
    else:
        genre_hints.append("hip-hop")

    if "melancholic" in moods:
        genre_hints.append("melodic")
    if "euphoric" in moods:
        genre_hints.append("club-ready")

    # Instrument hints from spectrum
    instruments = []
    if analysis["spectrum"]["bands_percent"].get("sub_bass", 0) > 15:
        instruments.append("heavy 808s")
    if analysis["spectrum"]["bands_percent"].get("brilliance", 0) > 10:
        instruments.append("crisp hi-hats")
    if "minor" in key:
        instruments.append("minor key synths")
    else:
        instruments.append("bright pads")

    parts = [
        ", ".join(genre_hints),
        f"{bpm} BPM",
        key,
        ", ".join(moods[:2]),
        ", ".join(instruments),
    ]

    return f"[{', '.join(parts)}]"


# ─── Plot Generation ────────────────────────────────────────────────────────

def generate_plots(y, sr, analysis, output_dir):
    """Generate visual analysis plots."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib
        matplotlib.use('Agg')
    except ImportError:
        print("WARNING: matplotlib not installed, skipping plots")
        return []

    plots = []

    # 1. Waveform + Energy
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), facecolor='#1a1a2e')
    for ax in axes:
        ax.set_facecolor('#16213e')
        ax.tick_params(colors='white')
        for spine in ax.spines.values():
            spine.set_color('#333')

    # Waveform
    times = np.linspace(0, len(y) / sr, num=len(y))
    axes[0].plot(times, y, color='#e94560', linewidth=0.3, alpha=0.8)
    axes[0].set_title('Waveform', color='white', fontsize=12, fontweight='bold')
    axes[0].set_xlabel('Time (s)', color='white')

    # Energy segments
    segments = analysis["energy"]["segments"]
    seg_times = np.linspace(0, len(y) / sr, num=len(segments))
    colors = ['#e94560' if e > 0.7 else '#0f3460' if e < 0.3 else '#533483' for e in segments]
    axes[1].bar(seg_times, segments, width=(seg_times[1] - seg_times[0]) * 0.9, color=colors, alpha=0.85)
    axes[1].set_title('Energy Profile', color='white', fontsize=12, fontweight='bold')
    axes[1].set_xlabel('Time (s)', color='white')
    axes[1].set_ylabel('Energy', color='white')

    # Spectrum bands
    bands = analysis["spectrum"]["bands_percent"]
    band_names = list(bands.keys())
    band_vals = list(bands.values())
    bar_colors = ['#e94560', '#ff6b6b', '#ffa502', '#ffd32a', '#7bed9f', '#70a1ff', '#5352ed']
    axes[2].barh(band_names, band_vals, color=bar_colors[:len(band_names)], alpha=0.85)
    axes[2].set_title('Frequency Spectrum Distribution', color='white', fontsize=12, fontweight='bold')
    axes[2].set_xlabel('Energy %', color='white')

    plt.tight_layout(pad=2)
    plot_path = os.path.join(output_dir, 'audio_analysis.png')
    plt.savefig(plot_path, dpi=150, facecolor='#1a1a2e', bbox_inches='tight')
    plt.close()
    plots.append(plot_path)
    print(f"  Plot saved: {plot_path}")

    return plots


# ─── Main Analysis ──────────────────────────────────────────────────────────

def analyze(audio_path, output_format="full", plot=False):
    """Run full analysis pipeline on an audio file."""
    print(f"\n🎵 Analyzing: {audio_path}")
    print("=" * 60)

    # Load audio
    print("  Loading audio...")
    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    duration = float(librosa.get_duration(y=y, sr=sr))
    print(f"  Duration: {timedelta(seconds=int(duration))} | Sample rate: {sr}Hz")

    # BPM
    print("  Detecting BPM...")
    bpm, bpm_conf, beat_frames = detect_bpm(y, sr)
    print(f"  BPM: {bpm} (confidence: {bpm_conf:.2f})")

    # Key
    print("  Detecting key...")
    key, key_conf = detect_key(y, sr)
    print(f"  Key: {key} (confidence: {key_conf:.2f})")

    # Energy
    print("  Analyzing energy...")
    energy = analyze_energy(y, sr)

    # Sections
    print("  Detecting sections...")
    sections = detect_sections(y, sr, duration)

    # Spectrum
    print("  Analyzing spectrum...")
    spectrum = analyze_spectrum(y, sr)

    # Mood
    print("  Classifying mood...")
    mood = classify_mood(y, sr, key, bpm, energy)

    # Build result
    result = {
        "file": os.path.basename(audio_path),
        "duration_seconds": round(duration, 1),
        "duration_formatted": str(timedelta(seconds=int(duration))),
        "bpm": {
            "tempo": bpm,
            "confidence": round(bpm_conf, 3),
        },
        "key": {
            "detected": key,
            "confidence": round(key_conf, 3),
        },
        "energy": energy,
        "sections": sections,
        "spectrum": spectrum,
        "mood": mood,
        "suno_prompt": generate_suno_prompt({
            "bpm": {"tempo": bpm},
            "key": {"detected": key},
            "mood": mood,
            "spectrum": spectrum,
        }),
    }

    # Plots
    if plot:
        print("  Generating plots...")
        output_dir = os.path.dirname(os.path.abspath(audio_path))
        plots = generate_plots(y, sr, result, output_dir)
        result["plots"] = plots

    # Output
    print("\n" + "=" * 60)

    if output_format == "json":
        print(json.dumps(result, indent=2))
    elif output_format == "text":
        print_text_report(result)
    else:
        print_text_report(result)
        print("\n── Raw JSON ──")
        print(json.dumps(result, indent=2))

    return result


def print_text_report(r):
    """Print a human-readable analysis report."""
    print(f"""
🎵 AUDIO ANALYSIS REPORT
{'=' * 50}
  File:     {r['file']}
  Duration: {r['duration_formatted']}
  BPM:      {r['bpm']['tempo']} (confidence: {r['bpm']['confidence']:.1%})
  Key:      {r['key']['detected']} (confidence: {r['key']['confidence']:.1%})

🎭 MOOD
  Detected: {', '.join(r['mood']['moods'])}
  Tonality: {r['mood']['tonality']}
  Brightness: {r['mood']['brightness']}

📊 ENERGY PROFILE
  Overall RMS: {r['energy']['overall_rms']}
  Dynamic Range: {r['energy']['dynamic_range']}
  Peak Segments: {r['energy']['peak_segments']}
  Drop Segments: {r['energy']['drop_segments']}
  Energy Map: {''.join(['█' if e > 0.7 else '▓' if e > 0.4 else '░' for e in r['energy']['segments']])}

🔊 SPECTRUM
  Dominant: {r['spectrum']['dominant_band']} — {r['spectrum']['character']}
  Sub-bass: {r['spectrum']['bands_percent']['sub_bass']}%
  Bass:     {r['spectrum']['bands_percent']['bass']}%
  Low-mid:  {r['spectrum']['bands_percent']['low_mid']}%
  Mid:      {r['spectrum']['bands_percent']['mid']}%
  Upper-mid:{r['spectrum']['bands_percent']['upper_mid']}%
  Presence: {r['spectrum']['bands_percent']['presence']}%
  Brilliance:{r['spectrum']['bands_percent']['brilliance']}%

📐 DETECTED SECTIONS""")

    for s in r['sections']:
        print(f"  [{s['index']}] {s['label']:>12} | {s['timestamp']} — {s['duration']}s")

    print(f"""
🎹 SUNO STYLE PROMPT
  {r['suno_prompt']}
""")


# ─── CLI Entry Point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Audio Analyzer — Songwriter Skill Support Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python audio_analyzer.py track.mp3
  python audio_analyzer.py beat.wav --output json
  python audio_analyzer.py demo.flac --plot --output full
        """,
    )
    parser.add_argument("audio_file", help="Path to audio file (mp3, wav, flac, ogg)")
    parser.add_argument("--output", choices=["json", "text", "full"], default="full",
                        help="Output format (default: full)")
    parser.add_argument("--plot", action="store_true",
                        help="Generate visual analysis plots")

    args = parser.parse_args()

    if not os.path.exists(args.audio_file):
        print(f"ERROR: File not found: {args.audio_file}")
        sys.exit(1)

    analyze(args.audio_file, args.output, args.plot)
