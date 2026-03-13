# Songwriter Toolkit

An AI-powered creative pipeline for writing rap lyrics, analyzing audio, storyboarding music videos, and generating Veo3 video prompts with start frames.

Built as a global skill for [Antigravity](https://antigravity.dev) — the AI coding assistant.

## What It Does

```
BEAT/AUDIO → Analyze → WRITE LYRICS → Suno Paste → STORYBOARD → Start Frames → VEO3 Generate
```

| Tool | Description |
|------|-------------|
| **Songwriter Skill** | Expert rap lyricist & Suno-format specialist — writes original lyrics across all hip-hop subgenres |
| **Audio Analyzer** | BPM, key, energy profile, section detection, spectrum analysis, mood classification from any audio file |
| **Veo3 Prompter** | Converts Suno-formatted lyrics into scene-by-scene video generation prompts |
| **Start Frame Generator** | Creates visual start frames for Veo3 using AI image generation |

## Quick Start

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Analyze a Beat

```bash
python scripts/audio_analyzer.py "path/to/beat.wav" --output text --plot
```

Output includes:
- BPM with confidence score
- Musical key (Krumhansl-Kessler detection)
- 16-segment energy profile with peak/drop detection
- Structural section boundaries
- 7-band frequency spectrum analysis
- Mood classification
- Auto-generated Suno style prompt
- Visual plots (waveform, energy, spectrum)

### Generate Video Storyboard

```bash
python scripts/veo3_prompter.py "path/to/lyrics.txt" --style cinematic --title "Song Title"
```

Visual styles: `cinematic` | `performance` | `abstract` | `narrative` | `hybrid`

### Interactive Mode

```bash
python scripts/veo3_prompter.py --interactive
```

## Installing as an Antigravity Skill

Copy or symlink the `skill/` directory into your Antigravity skills folder:

```powershell
# Windows
Copy-Item -Recurse skill\* "$env:USERPROFILE\.gemini\antigravity\skills\songwriter\"

# Or create a symlink
New-Item -ItemType Junction -Path "$env:USERPROFILE\.gemini\antigravity\skills\songwriter" -Target "$(Get-Location)\skill"
```

The skill activates automatically when you ask your AI assistant to write songs, analyze beats, or create music video storyboards.

## Project Structure

```
songwriter/
├── README.md
├── requirements.txt
├── .gitignore
├── LICENSE
├── skill/
│   └── SKILL.md                    # Antigravity skill definition
├── scripts/
│   ├── audio_analyzer.py           # Audio analysis engine
│   └── veo3_prompter.py            # Video storyboard generator
├── examples/
│   ├── memories_dont_die/
│   │   ├── lyrics.txt              # Example: full track lyrics
│   │   ├── storyboard.md           # Example: Veo3 storyboard
│   │   └── analysis.txt            # Example: audio analysis output
│   └── car_crash/
│       └── lyrics.txt              # Example: club banger lyrics
└── templates/
    ├── suno_style_prompts.md       # Reference: Suno style prompt formats
    └── veo3_scene_template.md      # Reference: Veo3 prompt structure
```

## Supported Genres

| Genre | BPM Range | Character |
|-------|-----------|-----------|
| Trap | 120-135 | 808 focus, hi-hat rolls, melodic hooks |
| Drill | 140-160 | Dark, menacing, staccato flow |
| Grime | 135-145 | High energy, choppy flow, London MC energy |
| Boom Bap | 85-100 | Sample-based, lyrical depth, complex rhymes |
| Cloud Rap | 60-80 | Dreamy, lo-fi, atmospheric |
| Rage | 140-170 | Distorted 808s, aggressive triplet flow |
| Melodic Rap | 120-145 | Auto-tune hooks, emotional vulnerability |
| Phonk | 120-140 | Southern-influenced, cowbell, dark aesthetics |

## Audio Analyzer Output Example

```
🎵 AUDIO ANALYSIS REPORT
==================================================
  File:     memories base.wav
  Duration: 0:05:11
  BPM:      129 (confidence: 65.1%)
  Key:      A# minor (confidence: 74.1%)

🎭 MOOD
  Detected: dark, aggressive, intense, vibrant

📊 ENERGY PROFILE
  Energy Map: ▓▓█████▓█▓██████

🔊 SPECTRUM
  Dominant: bass — punchy, warm bass foundation
  Sub-bass: 37.3%  |  Bass: 48.0%

🎹 SUNO STYLE PROMPT
  [trap, 129 BPM, A# minor, dark, aggressive, heavy 808s, minor key synths]
```

## License

MIT — see [LICENSE](LICENSE) for details.
