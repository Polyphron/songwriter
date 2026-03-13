# Veo3 Scene Prompt Template

Use this structure for each scene in a music video storyboard.

---

## Scene Template

```
SCENE [N] — [Song Section] | [Timestamp] | ~[Duration]s

VEO3 PROMPT:
[Detailed visual description. Include: style, subject, environment,
specific visual details. Camera: exact movement and lens. Lighting:
source, direction, color temperature. Motion: what moves and how.
Mood: emotional register. Film texture if relevant.]

NEGATIVE: [What to avoid — keeps Veo3 focused]
TRANSITION: [How this scene connects to the next]
KEY LYRIC: [The line driving the visuals]
```

---

## Prompt Anatomy

A strong Veo3 prompt has these layers:

### 1. Style & Texture
- Film format: "35mm film grain", "anamorphic widescreen", "Super 8"
- Visual style: "cinematic", "photorealistic", "stylized", "lo-fi"
- Color: specific palette, not vague ("cold blue-grey" not "dark")

### 2. Subject & Action
- Who: "a man", "a woman", "silhouette figure"
- What: "performing to camera", "walking through rain", "sitting still"
- Emotion: "with aggressive energy", "vulnerably", "with exhaustion"

### 3. Environment
- Where: specific ("dark warehouse with wet floor" not "room")
- Details: "graffiti walls", "single bare bulb", "rain-wet asphalt"
- Atmosphere: "heavy haze", "smoke", "dust particles", "fog"

### 4. Camera
- Type: "Steadicam", "handheld", "drone", "locked-off tripod"
- Movement: "slow push-in", "360° orbit", "tracking backward"
- Lens: "50mm", "35mm", "anamorphic", "wide-angle"
- DOF: "shallow depth of field", "deep focus", "rack focus"

### 5. Lighting
- Source: "single overhead", "rim light", "neon", "streetlight"
- Direction: "top-lit", "side-lit", "backlit", "under-lit"
- Color: "cold blue", "warm amber", "red neon", "mixed"
- Quality: "harsh", "soft", "dappled", "flickering"

### 6. Motion & Energy
- Speed: "slow-motion", "real-time", "time-lapse"
- Energy: "still", "building", "peak", "fading"
- Specific: "water splashing", "glass shattering", "smoke swirling"

---

## Start Frame Prompt Differences

Start frames need to nail ONE frame, not describe motion:

| Video Prompt | Start Frame Prompt |
|--------------|-------------------|
| "Camera slowly pushes in..." | "Close-up, 50mm lens, shallow DOF..." |
| "He walks through the rain..." | "Man standing in rain, mid-step..." |
| "Strobes pulsing..." | "Caught in a single strobe flash..." |
| "Water rising..." | "Ankle-deep black water on floor..." |

**Rule:** Freeze the most impactful moment of the scene.

---

## Visual Energy Mapping

| Song Section | Visual Energy | Camera | Lighting |
|-------------|--------------|--------|----------|
| Intro | Low, building | Slow, static | Dim, atmospheric |
| Verse | Medium-high | Tracking, medium shots | Directional, motivated |
| Hook/Chorus | Peak | Wide + push to close | Maximum contrast |
| Bridge | Shift/quiet | Locked-off, intimate | Single source |
| Beat switch | Reset-to-peak | Whip pan, match cut | Dramatic shift |
| Instrumental | Medium | Floating, observational | Atmospheric |
| Outro | Descending | Pull-back, fade | Cooling, dimming |
