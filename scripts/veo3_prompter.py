#!/usr/bin/env python3
"""
Veo3 Prompt Generator — Songwriter Skill Support Tool
Generates scene-by-scene video generation prompts from song lyrics.

This tool takes a Suno-formatted lyric sheet and produces structured Veo3
prompts for each section — complete with camera direction, lighting,
visual style, and motion description.

Usage:
    python veo3_prompter.py <lyrics_file> [--style cinematic|performance|abstract|narrative|hybrid]
    python veo3_prompter.py --interactive

Can also be imported and used programmatically.
"""

import argparse
import json
import re
import sys
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


# ─── Data Models ─────────────────────────────────────────────────────────────

@dataclass
class VeoScene:
    """A single Veo3 video generation prompt."""
    scene_number: int
    song_section: str
    duration_seconds: str
    prompt: str
    camera: str
    lighting: str
    motion: str
    mood: str
    transition_to_next: str
    lyrics_reference: str = ""
    negative_prompt: str = ""


@dataclass
class VeoStoryboard:
    """Complete video storyboard with all scenes."""
    title: str
    overall_style: str
    aspect_ratio: str = "16:9"
    total_scenes: int = 0
    color_palette: list = field(default_factory=list)
    scenes: list = field(default_factory=list)
    suno_style_prompt: str = ""


# ─── Visual Style Presets ────────────────────────────────────────────────────

STYLE_PRESETS = {
    "cinematic": {
        "description": "Film-grade cinematography, shallow depth of field, lens flares, anamorphic widescreen",
        "default_camera": "Steadicam tracking shot",
        "default_lighting": "High contrast, motivated lighting, golden hour or neon",
        "color_palette": ["deep blacks", "warm highlights", "teal shadows", "amber accents"],
        "negative": "amateur, shaky, low quality, bright flat lighting",
    },
    "performance": {
        "description": "Live performance energy, stage lighting, crowd shots, sweat and grit",
        "default_camera": "Handheld with controlled shake, quick cuts",
        "default_lighting": "Stage spotlights, strobe effects, moving beam lights",
        "color_palette": ["stark white spots", "deep red", "electric blue", "smoke haze"],
        "negative": "static, boring, empty stage, daytime",
    },
    "abstract": {
        "description": "Artistic, surreal visuals, fluid motion, impossible geometry",
        "default_camera": "Floating omniscient camera, impossible angles",
        "default_lighting": "Volumetric god rays, bioluminescence, particle effects",
        "color_palette": ["iridescent", "chromatic aberration", "deep violet", "liquid gold"],
        "negative": "realistic, mundane, office, suburban",
    },
    "narrative": {
        "description": "Story-driven short film style, character-focused, emotional arcs",
        "default_camera": "Close-ups and medium shots, motivated movement",
        "default_lighting": "Natural and practical lighting, atmospheric",
        "color_palette": ["desaturated base", "single accent color", "shadow detail", "skin tones"],
        "negative": "music video cliché, flashy, over-produced",
    },
    "hybrid": {
        "description": "Mix of performance and cinematic narrative, switches between worlds",
        "default_camera": "Alternating between steadicam and handheld",
        "default_lighting": "Contrast between warm narrative and cool performance",
        "color_palette": ["split toning", "neon vs natural", "smoke gradients", "chrome reflections"],
        "negative": "monotone, single setting, static camera",
    },
}


# ─── Section Visual Mapping ─────────────────────────────────────────────────

SECTION_VISUALS = {
    "intro": {
        "energy": "building",
        "camera_default": "Slow push-in or aerial descent",
        "lighting_default": "Dim, atmospheric, silhouettes",
        "motion_default": "Slow motion, particles in air, breath visible",
        "mood_default": "anticipation, tension building",
    },
    "verse": {
        "energy": "medium-high",
        "camera_default": "Tracking shot following subject, medium close-up",
        "lighting_default": "Directional, motivated by environment",
        "motion_default": "Walking/moving through space, environment reveals",
        "mood_default": "storytelling, intensity building",
    },
    "hook": {
        "energy": "peak",
        "camera_default": "Wide establishing then quick push to close-up",
        "lighting_default": "Maximum contrast, strobes or dramatic shift",
        "motion_default": "Fast cuts, high energy, choreography or crowd",
        "mood_default": "release, euphoria, maximum impact",
    },
    "chorus": {
        "energy": "peak",
        "camera_default": "Sweeping crane shot or drone pull-back",
        "lighting_default": "Full wash, vibrant, lens flares",
        "motion_default": "Expansive, crowd, cityscape, or abstract explosion",
        "mood_default": "anthemic, powerful, sing-along energy",
    },
    "bridge": {
        "energy": "shift",
        "camera_default": "Locked-off or slow dolly, intimate framing",
        "lighting_default": "Single source, vulnerability",
        "motion_default": "Stillness or slow rotation, time feels suspended",
        "mood_default": "vulnerability, shift in perspective, rawness",
    },
    "beat switch": {
        "energy": "reset-to-peak",
        "camera_default": "Whip pan or match cut to entirely new environment",
        "lighting_default": "Dramatic shift — warm to cold or vice versa",
        "motion_default": "Sudden change in speed/style, visual disruption",
        "mood_default": "surprise, gear shift, new energy",
    },
    "instrumental break": {
        "energy": "medium",
        "camera_default": "Floating, observational, b-roll aesthetic",
        "lighting_default": "Atmospheric, volumetric, environmental",
        "motion_default": "Slow-motion details, texture shots, cutaways",
        "mood_default": "breathing room, visual storytelling without vocals",
    },
    "outro": {
        "energy": "descending",
        "camera_default": "Slow pull-back or fade, increasing distance",
        "lighting_default": "Fading, cooling, dawn or twilight shift",
        "motion_default": "Gradual slowdown, final moment held",
        "mood_default": "resolution, echo, lingering",
    },
}


# ─── Lyrics Parser ──────────────────────────────────────────────────────────

def parse_lyrics(text):
    """Parse Suno-formatted lyrics into sections."""
    sections = []
    current_section = None
    current_lyrics = []

    for line in text.strip().split('\n'):
        line = line.strip()

        # Match section headers like [Verse 1], [Hook], [Instrumental Break — 8 bars]
        section_match = re.match(r'^\[([^\]]+)\]$', line)

        if section_match:
            # Save previous section
            if current_section:
                sections.append({
                    "label": current_section,
                    "type": classify_section(current_section),
                    "lyrics": '\n'.join(current_lyrics).strip(),
                })
            current_section = section_match.group(1)
            current_lyrics = []
        elif line and current_section:
            current_lyrics.append(line)

    # Save last section
    if current_section:
        sections.append({
            "label": current_section,
            "type": classify_section(current_section),
            "lyrics": '\n'.join(current_lyrics).strip(),
        })

    return sections


def classify_section(label):
    """Map a section label to a visual type."""
    label_lower = label.lower()

    if "intro" in label_lower:
        return "intro"
    elif "outro" in label_lower:
        return "outro"
    elif "hook" in label_lower:
        return "hook"
    elif "chorus" in label_lower:
        return "chorus"
    elif "verse" in label_lower:
        return "verse"
    elif "bridge" in label_lower:
        return "bridge"
    elif "beat switch" in label_lower:
        return "beat switch"
    elif "instrumental" in label_lower or "break" in label_lower:
        return "instrumental break"
    elif "pre-chorus" in label_lower or "pre chorus" in label_lower:
        return "verse"  # visually treat as buildup
    else:
        return "verse"  # safe default


# ─── Scene Generator ────────────────────────────────────────────────────────

def generate_scene(section, scene_num, style_preset, total_sections):
    """Generate a Veo3 scene prompt from a song section."""
    sec_type = section["type"]
    visuals = SECTION_VISUALS.get(sec_type, SECTION_VISUALS["verse"])
    style = STYLE_PRESETS[style_preset]

    # Estimate duration
    lyrics = section["lyrics"]
    if not lyrics or "instrumental" in section["label"].lower():
        duration = "8-12"
    elif sec_type in ("hook", "chorus"):
        duration = "10-15"
    elif sec_type in ("intro", "outro"):
        duration = "6-10"
    else:
        line_count = len([l for l in lyrics.split('\n') if l.strip()])
        duration = f"{max(8, line_count * 2)}-{max(12, line_count * 3)}"

    # Extract visual keywords from lyrics
    visual_keywords = extract_visual_cues(lyrics) if lyrics else []

    # Build the main prompt
    prompt_parts = [
        style["description"],
    ]

    if visual_keywords:
        prompt_parts.append(f"Visual elements: {', '.join(visual_keywords[:5])}")

    if lyrics:
        # Take first 1-2 lines for mood reference
        first_lines = lyrics.split('\n')[:2]
        lyric_mood = ' / '.join([l.strip() for l in first_lines if l.strip()])
        prompt_parts.append(f"Lyrics convey: {lyric_mood}")

    prompt_parts.append(f"Energy level: {visuals['energy']}")

    prompt = '. '.join(prompt_parts)

    # Transition logic
    if scene_num < total_sections:
        if sec_type in ("verse", "intro"):
            transition = "Cut on beat — quick transition to next section"
        elif sec_type in ("hook", "chorus"):
            transition = "Sustained hold, then smooth dissolve"
        elif sec_type == "bridge":
            transition = "Slow fade or whip pan to new energy"
        elif sec_type == "instrumental break":
            transition = "Build tension, snap cut on downbeat"
        else:
            transition = "Match cut or beat-synced transition"
    else:
        transition = "Fade to black"

    return VeoScene(
        scene_number=scene_num,
        song_section=section["label"],
        duration_seconds=duration,
        prompt=prompt,
        camera=visuals["camera_default"],
        lighting=visuals["lighting_default"],
        motion=visuals["motion_default"],
        mood=visuals["mood_default"],
        transition_to_next=transition,
        lyrics_reference=lyrics[:200] if lyrics else "(instrumental)",
        negative_prompt=style["negative"],
    )


def extract_visual_cues(lyrics):
    """Extract visually evocative words from lyrics for scene prompting."""
    visual_words = {
        # Colors & Light
        "red", "blue", "gold", "silver", "black", "white", "neon", "chrome",
        "glow", "flash", "dark", "bright", "shadow", "light", "flame", "fire",
        "smoke", "mist", "haze",
        # Places
        "street", "club", "city", "roof", "alley", "highway", "bridge",
        "ocean", "sky", "rain", "storm", "night", "dawn", "sunset",
        "dance floor", "stage", "studio", "penthouse", "basement",
        # Objects
        "diamonds", "ice", "glass", "mirror", "chains", "crown", "blade",
        "car", "whip", "cash", "throne", "silk", "velvet",
        # Actions
        "running", "falling", "flying", "dancing", "burning", "breaking",
        "spinning", "crashing", "rising", "sinking", "racing",
        # Atmosphere
        "sweat", "blood", "tears", "scars", "tattoo", "ink",
    }

    found = []
    lyrics_lower = lyrics.lower()

    for word in visual_words:
        if word in lyrics_lower:
            found.append(word)

    return found


# ─── Storyboard Builder ─────────────────────────────────────────────────────

def build_storyboard(lyrics_text, style="cinematic", title="Untitled"):
    """Build a complete Veo3 storyboard from lyrics."""
    sections = parse_lyrics(lyrics_text)

    if not sections:
        print("ERROR: No sections found. Make sure lyrics use [Section] format.")
        return None

    style_data = STYLE_PRESETS.get(style, STYLE_PRESETS["cinematic"])

    storyboard = VeoStoryboard(
        title=title,
        overall_style=style_data["description"],
        color_palette=style_data["color_palette"],
        total_scenes=len(sections),
    )

    # Try to extract Suno style prompt
    first_section = sections[0]
    if first_section["type"] == "intro" and not first_section["lyrics"]:
        # Check if the label itself is a style prompt
        pass

    for i, section in enumerate(sections, 1):
        scene = generate_scene(section, i, style, len(sections))
        storyboard.scenes.append(scene)

    return storyboard


# ─── Output Formatters ──────────────────────────────────────────────────────

def format_veo3_prompts(storyboard):
    """Format storyboard as individual Veo3 copy-paste prompts."""
    output = []
    output.append(f"{'=' * 70}")
    output.append(f"🎬 VEO3 STORYBOARD: {storyboard.title}")
    output.append(f"{'=' * 70}")
    output.append(f"Style: {storyboard.overall_style}")
    output.append(f"Palette: {', '.join(storyboard.color_palette)}")
    output.append(f"Aspect Ratio: {storyboard.aspect_ratio}")
    output.append(f"Total Scenes: {storyboard.total_scenes}")
    output.append("")

    for scene in storyboard.scenes:
        output.append(f"{'─' * 70}")
        output.append(f"SCENE {scene.scene_number} — [{scene.song_section}]")
        output.append(f"Duration: ~{scene.duration_seconds}s")
        output.append(f"{'─' * 70}")
        output.append("")
        output.append("📋 VEO3 PROMPT (copy-paste ready):")
        output.append(f"┌{'─' * 68}┐")

        # Build the actual Veo3 prompt
        veo_prompt = (
            f"{scene.prompt}. "
            f"Camera: {scene.camera}. "
            f"Lighting: {scene.lighting}. "
            f"Motion: {scene.motion}. "
            f"Mood: {scene.mood}."
        )
        # Word wrap at 66 chars
        words = veo_prompt.split()
        lines = []
        current = ""
        for w in words:
            if len(current) + len(w) + 1 > 66:
                lines.append(current)
                current = w
            else:
                current = f"{current} {w}".strip()
        if current:
            lines.append(current)

        for line in lines:
            output.append(f"│ {line:<66} │")
        output.append(f"└{'─' * 68}┘")
        output.append("")

        if scene.negative_prompt:
            output.append(f"  ❌ Negative: {scene.negative_prompt}")

        output.append(f"  🔄 Transition: {scene.transition_to_next}")

        if scene.lyrics_reference and scene.lyrics_reference != "(instrumental)":
            output.append(f"  📝 Lyrics: {scene.lyrics_reference[:100]}...")

        output.append("")

    return '\n'.join(output)


def format_json(storyboard):
    """Format storyboard as JSON for programmatic use."""
    data = {
        "title": storyboard.title,
        "overall_style": storyboard.overall_style,
        "aspect_ratio": storyboard.aspect_ratio,
        "color_palette": storyboard.color_palette,
        "total_scenes": storyboard.total_scenes,
        "scenes": [asdict(s) for s in storyboard.scenes],
    }
    return json.dumps(data, indent=2)


# ─── CLI Entry Point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Veo3 Prompt Generator — Generate video prompts from song lyrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Styles:
  cinematic    — Film-grade, shallow DOF, lens flares, widescreen
  performance  — Stage energy, strobes, crowd shots
  abstract     — Surreal, fluid, impossible geometry
  narrative    — Story-driven, character-focused
  hybrid       — Mix of performance and cinematic

Examples:
  python veo3_prompter.py lyrics.txt --style cinematic
  python veo3_prompter.py song.txt --style performance --title "Car Crash"
  python veo3_prompter.py song.txt --output json
        """,
    )
    parser.add_argument("lyrics_file", nargs="?", help="Path to lyrics file (Suno format)")
    parser.add_argument("--style", choices=list(STYLE_PRESETS.keys()), default="cinematic",
                        help="Visual style preset (default: cinematic)")
    parser.add_argument("--title", default="Untitled", help="Song title")
    parser.add_argument("--output", choices=["text", "json"], default="text",
                        help="Output format")
    parser.add_argument("--interactive", action="store_true",
                        help="Paste lyrics interactively")

    args = parser.parse_args()

    if args.interactive:
        print("Paste your Suno-formatted lyrics below.")
        print("When done, enter an empty line then type END:")
        lines = []
        while True:
            try:
                line = input()
                if line.strip().upper() == "END":
                    break
                lines.append(line)
            except EOFError:
                break
        lyrics_text = '\n'.join(lines)
    elif args.lyrics_file:
        if not os.path.exists(args.lyrics_file):
            print(f"ERROR: File not found: {args.lyrics_file}")
            sys.exit(1)
        with open(args.lyrics_file, 'r', encoding='utf-8') as f:
            lyrics_text = f.read()
    else:
        parser.print_help()
        sys.exit(1)

    storyboard = build_storyboard(lyrics_text, args.style, args.title)

    if storyboard:
        if args.output == "json":
            print(format_json(storyboard))
        else:
            print(format_veo3_prompts(storyboard))
