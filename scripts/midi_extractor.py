#!/usr/bin/env python3
"""
MIDI Extractor v2 — Songwriter Toolkit
========================================
High-quality audio-to-MIDI conversion with multiple backends.

Backends:
    crepe    — torchcrepe (BEST for monophonic: vocals, bass). 
               State-of-art neural pitch detection. Very clean output.
    pyin     — librosa pYIN (GOOD for monophonic, no extra deps).
               Probabilistic YIN, reliable and fast.
    basic    — basic-pitch (OK for polyphonic: chords, full mix).
               Spotify's multi-pitch detector. Noisier but handles chords.

Usage:
    # Best quality vocal MIDI (use CREPE on isolated vocal stem)
    python midi_extractor.py "vocals.wav" --backend crepe

    # Quick extraction (pYIN, no extra deps)
    python midi_extractor.py "vocals.wav" --backend pyin

    # Polyphonic content (chords, keys, full mix)
    python midi_extractor.py "other.wav" --backend basic

    # Full stem pipeline (extracts MIDI from all stems)
    python midi_extractor.py --stems-dir "./stems_hq/htdemucs_ft/trackname"

Requirements:
    crepe backend:  pip install torchcrepe torch
    pyin backend:   (included with librosa — no extra install)
    basic backend:  pip install basic-pitch
"""

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import librosa


def midi_to_note_name(midi_pitch):
    """Convert MIDI pitch number to note name."""
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = (midi_pitch // 12) - 1
    name = names[midi_pitch % 12]
    return f"{name}{octave}"


def hz_to_midi(freq):
    """Convert frequency in Hz to MIDI pitch number."""
    if freq <= 0:
        return 0
    return int(round(69 + 12 * np.log2(freq / 440.0)))


def note_to_hz(note_str: str) -> float:
    """Convert note name (e.g., 'C3') to frequency in Hz."""
    names = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    note_str = note_str.strip().upper()
    if "#" in note_str:
        base = names.get(note_str[0], 0) + 1
        octave = int(note_str[2:])
    else:
        base = names.get(note_str[0], 0)
        octave = int(note_str[1:])
    midi = base + (octave + 1) * 12
    return 440.0 * (2 ** ((midi - 69) / 12.0))


def create_midi_from_notes(notes, output_path, tempo=120):
    """Create a MIDI file from a list of (start, end, pitch, velocity) tuples."""
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    instrument = pretty_midi.Instrument(program=0, name="Extracted")

    for start, end, pitch, velocity in notes:
        if end > start and 0 < pitch < 128:
            note = pretty_midi.Note(
                velocity=int(velocity),
                pitch=int(pitch),
                start=float(start),
                end=float(end),
            )
            instrument.notes.append(note)

    midi.instruments.append(instrument)
    midi.write(str(output_path))
    return midi


def extract_crepe(audio_path, sr=16000, min_confidence=0.7, min_duration=0.05):
    """
    Extract MIDI using torchcrepe — highest quality monophonic pitch detection.
    """
    import torch
    import torchcrepe

    print(f"  Loading audio at {sr}Hz...")
    y, _ = librosa.load(str(audio_path), sr=sr, mono=True)
    audio_tensor = torch.tensor(y).unsqueeze(0)

    print(f"  Running CREPE pitch detection (this is the good one)...")
    start_time = time.time()

    # Run CREPE — 'full' model for best quality
    pitch, confidence = torchcrepe.predict(
        audio_tensor,
        sr,
        hop_length=80,  # ~5ms resolution at 16kHz
        fmin=50,
        fmax=2000,
        model='full',
        decoder=torchcrepe.decode.viterbi,  # Viterbi smoothing for cleaner pitch
        return_periodicity=True,
        batch_size=1024,
        device='cuda' if torch.cuda.is_available() else 'cpu',
    )

    elapsed = time.time() - start_time
    print(f"  CREPE inference done ({elapsed:.1f}s)")

    # Convert to numpy
    pitch = pitch.squeeze().numpy()
    confidence = confidence.squeeze().numpy()

    # Filter by confidence
    pitch[confidence < min_confidence] = 0

    # Convert pitch trajectory to discrete notes
    hop_time = 80 / sr  # time per frame
    notes = []
    current_midi = 0
    note_start = 0
    note_frames = 0

    for i, (freq, conf) in enumerate(zip(pitch, confidence)):
        t = i * hop_time

        if freq > 0 and conf >= min_confidence:
            midi_pitch = hz_to_midi(freq)

            if midi_pitch != current_midi:
                # End previous note
                if current_midi > 0 and note_frames > 0:
                    note_end = t
                    duration = note_end - note_start
                    if duration >= min_duration:
                        avg_conf = min(127, int(conf * 127))
                        notes.append((note_start, note_end, current_midi, avg_conf))

                # Start new note
                current_midi = midi_pitch
                note_start = t
                note_frames = 1
            else:
                note_frames += 1
        else:
            # Silence — end current note
            if current_midi > 0 and note_frames > 0:
                note_end = t
                duration = note_end - note_start
                if duration >= min_duration:
                    avg_conf = min(127, int(0.8 * 127))
                    notes.append((note_start, note_end, current_midi, avg_conf))

            current_midi = 0
            note_frames = 0

    # Close final note
    if current_midi > 0 and note_frames > 0:
        note_end = len(pitch) * hop_time
        duration = note_end - note_start
        if duration >= min_duration:
            notes.append((note_start, note_end, current_midi, 100))

    return notes, elapsed


def extract_pyin(audio_path, sr=22050, min_duration=0.05):
    """
    Extract MIDI using librosa's pYIN — good quality, no extra deps.
    """
    print(f"  Loading audio at {sr}Hz...")
    y, _ = librosa.load(str(audio_path), sr=sr, mono=True)

    print(f"  Running pYIN pitch detection...")
    start_time = time.time()

    f0, voiced_flag, voiced_probs = librosa.pyin(
        y, sr=sr,
        fmin=librosa.note_to_hz('C2'),
        fmax=librosa.note_to_hz('C7'),
        frame_length=2048,
    )

    elapsed = time.time() - start_time
    print(f"  pYIN done ({elapsed:.1f}s)")

    hop_time = 512 / sr  # default hop length
    notes = []
    current_midi = 0
    note_start = 0

    for i, (freq, voiced) in enumerate(zip(f0, voiced_flag)):
        t = i * hop_time

        if voiced and not np.isnan(freq) and freq > 0:
            midi_pitch = hz_to_midi(freq)

            if midi_pitch != current_midi:
                if current_midi > 0:
                    duration = t - note_start
                    if duration >= min_duration:
                        notes.append((note_start, t, current_midi, 100))

                current_midi = midi_pitch
                note_start = t
            # else: continue current note
        else:
            if current_midi > 0:
                duration = t - note_start
                if duration >= min_duration:
                    notes.append((note_start, t, current_midi, 100))
                current_midi = 0

    # Close final note
    if current_midi > 0:
        t_end = len(f0) * hop_time
        duration = t_end - note_start
        if duration >= min_duration:
            notes.append((note_start, t_end, current_midi, 100))

    return notes, elapsed


def extract_basic(audio_path):
    """
    Extract MIDI using basic-pitch — for polyphonic content.
    """
    from basic_pitch.inference import predict

    print(f"  Running basic-pitch inference...")
    start_time = time.time()

    model_output, midi_data, note_events = predict(
        str(audio_path),
        onset_threshold=0.5,
        frame_threshold=0.3,
        melodia_trick=True,
    )

    elapsed = time.time() - start_time
    print(f"  basic-pitch done ({elapsed:.1f}s)")

    notes = []
    for n in note_events:
        start_t, end_t, pitch = n[0], n[1], n[2]
        vel = n[3] if len(n) > 3 else 80
        notes.append((start_t, end_t, pitch, vel))

    return notes, elapsed


def run_extraction(audio_path, backend, output_path=None, save_csv=False,
                   save_plot=False, min_confidence=0.7, min_duration=0.05):
    """Main extraction function."""
    audio_path = Path(audio_path).resolve()

    if not audio_path.exists():
        print(f"  ❌ File not found: {audio_path}")
        sys.exit(1)

    if output_path is None:
        output_path = audio_path.parent / f"{audio_path.stem}.mid"
    else:
        output_path = Path(output_path).resolve()

    backend_names = {
        "crepe": "torchcrepe (neural pitch, monophonic, highest quality)",
        "pyin": "librosa pYIN (probabilistic, monophonic, fast)",
        "basic": "basic-pitch (Spotify, polyphonic)",
    }

    print(f"\n🎹 MIDI EXTRACTOR v2")
    print(f"{'=' * 60}")
    print(f"  Input:      {audio_path.name}")
    print(f"  Output:     {output_path.name}")
    print(f"  Backend:    {backend_names.get(backend, backend)}")
    if backend == "crepe":
        print(f"  Confidence: {min_confidence}")
    print(f"  Min note:   {min_duration}s")
    print()

    # Run extraction
    if backend == "crepe":
        notes, elapsed = extract_crepe(audio_path, min_confidence=min_confidence,
                                        min_duration=min_duration)
    elif backend == "pyin":
        notes, elapsed = extract_pyin(audio_path, min_duration=min_duration)
    elif backend == "basic":
        notes, elapsed = extract_basic(audio_path)
    else:
        print(f"  ❌ Unknown backend: {backend}")
        sys.exit(1)

    if not notes:
        print(f"\n  ⚠️  No notes detected. Try lowering --min-confidence or using a different backend.")
        return

    # Create MIDI
    create_midi_from_notes(notes, output_path)

    # Analyze
    pitches = [n[2] for n in notes]
    durations = [n[1] - n[0] for n in notes]

    from collections import Counter
    pitch_counts = Counter(pitches)
    top_notes = pitch_counts.most_common(5)
    top_str = ", ".join(f"{midi_to_note_name(p)} ({c}×)" for p, c in top_notes)

    min_p, max_p = min(pitches), max(pitches)

    print(f"\n{'=' * 60}")
    print(f"✅ MIDI EXTRACTED ({elapsed:.1f}s)")
    print(f"{'=' * 60}")
    print(f"  📄 MIDI file:     {output_path}")
    print(f"  🎵 Notes found:   {len(notes)}")
    print(f"  🎹 Note range:    {midi_to_note_name(min_p)} — {midi_to_note_name(max_p)} (MIDI {min_p}—{max_p})")
    print(f"  ⏱️  Avg duration:  {np.mean(durations):.3f}s")
    print(f"  📊 Top notes:     {top_str}")

    # CSV
    if save_csv:
        csv_path = output_path.with_suffix(".csv")
        with open(csv_path, "w") as f:
            f.write("start,end,midi_pitch,note,velocity,duration\n")
            for s, e, p, v in notes:
                f.write(f"{s:.4f},{e:.4f},{p},{midi_to_note_name(p)},{v},{e-s:.4f}\n")
        print(f"  📊 CSV saved:     {csv_path}")

    # Plot
    if save_plot:
        try:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(16, 6))
            for s, e, p, v in notes:
                intensity = v / 127.0
                ax.barh(p, e - s, left=s, height=0.8,
                        color=(0.3, 0.5, 1.0, 0.3 + intensity * 0.7),
                        edgecolor=(0.2, 0.3, 0.8, 0.5), linewidth=0.5)
            ax.set_xlabel("Time (s)", fontsize=12)
            ax.set_ylabel("MIDI Pitch", fontsize=12)
            ax.set_title(f"Piano Roll — {audio_path.stem} ({backend})", fontsize=14)
            ax.grid(True, alpha=0.3)
            yticks = range(min_p, max_p + 1, 2)
            ax.set_yticks(list(yticks))
            ax.set_yticklabels([midi_to_note_name(p) for p in yticks], fontsize=8)
            plt.tight_layout()
            plot_path = output_path.with_suffix(".png")
            plt.savefig(plot_path, dpi=150)
            plt.close()
            print(f"  🎨 Plot saved:    {plot_path}")
        except ImportError:
            print(f"  ⚠️  matplotlib not found — skipping plot")

    print()
    return notes


def run_stems_pipeline(stems_dir, output_dir=None, save_csv=False, save_plot=False):
    """Extract MIDI from all stems in a directory."""
    stems_dir = Path(stems_dir).resolve()

    if not stems_dir.exists():
        print(f"  ❌ Stems directory not found: {stems_dir}")
        sys.exit(1)

    if output_dir is None:
        output_dir = stems_dir.parent / "midi"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Define which backend to use for each stem type
    stem_backends = {
        "vocals": "crepe",   # Monophonic — CREPE is king
        "bass": "crepe",     # Monophonic — CREPE handles bass well
        "drums": None,       # Skip — drums don't have pitch
        "other": "basic",    # Polyphonic — synths, keys, etc.
        "guitar": "crepe",   # Monophonic-ish
        "piano": "basic",    # Polyphonic
    }

    print(f"\n🎹 MIDI STEM PIPELINE")
    print(f"{'=' * 60}")
    print(f"  Stems dir:  {stems_dir}")
    print(f"  Output dir: {output_dir}")
    print()

    results = {}

    for stem_file in sorted(stems_dir.iterdir()):
        if not stem_file.is_file():
            continue
        if stem_file.suffix not in [".wav", ".mp3", ".flac"]:
            continue

        stem_name = stem_file.stem.lower()
        backend = stem_backends.get(stem_name)

        if backend is None:
            print(f"  ⏭️  Skipping {stem_name} (no pitch content)")
            continue

        output_path = output_dir / f"{stem_name}.mid"

        print(f"\n{'─' * 60}")
        print(f"  🎚️  Processing: {stem_name} → {backend} backend")

        notes = run_extraction(
            stem_file, backend,
            output_path=output_path,
            save_csv=save_csv,
            save_plot=save_plot,
        )

        if notes:
            results[stem_name] = {
                "notes": len(notes),
                "midi": str(output_path),
                "backend": backend,
            }

    print(f"\n{'=' * 60}")
    print(f"✅ STEM PIPELINE COMPLETE")
    print(f"{'=' * 60}")
    for stem, info in results.items():
        print(f"  🎚️  {stem:12s}  {info['notes']:4d} notes  ({info['backend']})")
    print(f"\n  📁 Output: {output_dir}")
    print()

    return results


def main():
    parser = argparse.ArgumentParser(
        description="High-quality audio-to-MIDI extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Backends:
  crepe   torchcrepe — BEST for monophonic (vocals, bass). Neural pitch.
  pyin    librosa pYIN — GOOD for monophonic. Fast, no extra deps.
  basic   basic-pitch — OK for polyphonic (chords, keys, full mix).

Examples:
  %(prog)s "vocals.wav" --backend crepe          (best vocals)
  %(prog)s "bass.wav" --backend crepe             (best bass)
  %(prog)s "other.wav" --backend basic            (polyphonic)
  %(prog)s "vocals.wav" --backend pyin            (quick, no extra deps)
  %(prog)s --stems-dir "./stems/htdemucs_ft/track" (full pipeline)
        """,
    )

    parser.add_argument("audio", nargs="?", help="Path to audio file")
    parser.add_argument(
        "--backend", "-b", default="crepe",
        choices=["crepe", "pyin", "basic"],
        help="Extraction backend (default: crepe)",
    )
    parser.add_argument("--output", "-o", default=None, help="Output MIDI path")
    parser.add_argument(
        "--stems-dir", default=None,
        help="Process all stems in directory (auto-selects best backend per stem)",
    )
    parser.add_argument("--save-csv", action="store_true", help="Save CSV")
    parser.add_argument("--save-plot", action="store_true", help="Save piano roll")
    parser.add_argument(
        "--min-confidence", type=float, default=0.7,
        help="Min confidence for CREPE (0-1, default: 0.7)",
    )
    parser.add_argument(
        "--min-duration", type=float, default=0.05,
        help="Min note duration in seconds (default: 0.05)",
    )

    args = parser.parse_args()

    if args.stems_dir:
        run_stems_pipeline(args.stems_dir, save_csv=args.save_csv,
                           save_plot=args.save_plot)
    elif args.audio:
        run_extraction(
            args.audio, args.backend,
            output_path=args.output,
            save_csv=args.save_csv,
            save_plot=args.save_plot,
            min_confidence=args.min_confidence,
            min_duration=args.min_duration,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
