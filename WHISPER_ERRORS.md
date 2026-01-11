# Whisper Transcription Error Fixing Guide

This document explains common transcription errors that occur when using OpenAI Whisper for game audio files and how to fix them.

## Character Name Mapping

The file names use internal character names that differ from display names. Here's the mapping:

| Display Name | Internal Names (in filenames) |
|--------------|------------------------------|
| Holliday | astro |
| Infernus | inferno |
| Abrams | atlas |
| Vindicta | hornet |
| Calico | nano |
| Mo and Krill | digger, krill |
| Fathom | slork |
| Paradox | chrono |
| Dynamo | sumo, dynano, prof |
| McGinnis | forge |
| Lady Geist | ghost, geist |
| Seven | gigawatt |
| Grey Talon | orion |
| Pocket | synth, fairfax |
| Ivy | tengu |
| Vyper | viper, kali |
| Billy | punkgoat |
| Mina | vampirebat, vampriebat |
| Victor | frank |
| Paige | bookworm |
| Sinclair (Henry) | magician_henry |
| Sinclair (Savannah) | magician_savannah |
| Sinclair | magician |
| The Boss | the_boss |

## Common Whisper Transcription Errors

Based on analysis of the transcript data, here are the most frequent error patterns with their occurrence counts:

### Error Frequency Summary

| Error Pattern | Affected Files |
|---------------|----------------|
| Paige (bookworm) → Page/Pyke | ~199 files |
| Operative → Raven | ~147 files |
| Infernus → Furnace | ~54 files |
| Wraith → Race/Raid/Rate | ~52 files |
| Stun → Stone/Stan/Stand | ~38 files |
| Doorman → Torment/Dormant | ~7 files |

### 1. Character Name Misrecognition

Whisper often struggles with unusual or game-specific names. Common patterns include:

| Original Name | Common Whisper Errors |
|---------------|----------------------|
| **Operative** | **Raven** (consistently misrecognized in ~147 files) |
| **Wraith** | Race, Raid, Rate, Rates, Raze (52+ files) |
| **Infernus** | Furnace, "And Furnace" (54+ files) |
| **Paige** | Page, Pyke (199+ files in bookworm context) |
| **Victor** | Victory, Fixers, Figs, Pictures |
| Doorman | Dormin, Dorman, Doman, Dolmen, Doughman, Tolman, Dormant, Dormands, Torment, Dormammu |
| Graf | Graph, Graphs, Grath, Grafton |
| Venator | Venera, Venetus, Betterless |
| Fathom | Fatum, Rathom, "Don't fathom" (for "Stun Fathom") |
| Haze | Hayes, Hace, "Stoned heads" (for "Stun Haze") |
| Krill | Quill, Grill, Quills, Grin |
| Viscous | Viscus |
| Kelvin | Kelphin, Kermin |
| Sinclair | Clairborne, Clear |
| Ivy | Hyvie, Ivey |
| Calico | Talico, Gallico, Colicle |
| Trapper | "Gun trapper" (for "Stun Trapper") |
| Vyper | "Darn Vyper" (for "Stun Vyper") |
| Seven | 7, Se7en, Stanton |
| McGinnis | McInnes, McGuinness, Guinness |
| Grey Talon | Talon, Greytaran |
| Mina | Meta, Stamina |

### 2. Action Word Errors

Gaming terms are often misrecognized:

| Correct | Common Errors |
|---------|---------------|
| Stun | Stone, Stan, Stand, Stoned, Done, Don't, Dun, Gun, Darn, Startin' |
| Heal | Hear |

Note: "Stun X" is frequently misheard as compound words or variations:
- "Stonecolicle" → "Stun Calico"
- "Stonefathom" → "Stun Fathom"
- "Stangeist" → "Stun Geist"
- "Stoned bebop" → "Stun Bebop"
- "Stand the dorm in" → "Stun Doorman"

### 3. Homophone Confusions

| Correct Context | Error |
|-----------------|-------|
| "I can heal you" | "I can hear you" |
| "what X bought" | "what X brought" |
| "took out X" | "took our X" |
| "They took out" | "He/She/It took out" |
| "Mina, I can heal ya" | "Meta, I can heal ya" |

### 4. Phrase-Level Misrecognitions

| Incorrect | Correct |
|-----------|---------|
| "I saw a raven" | "I saw Operative" |
| "Raven's in mid" | "Operative's in mid" |
| "Race on the bridge" | "Wraith's on the bridge" |
| "And Furnace is dead" | "Infernus is dead" |
| "Victory is in mid" | "Victor's in mid" |
| "Page is missing" | "Paige is missing" |
| "Assault X" | "I saw X" |
| "Let's talk about X" | "They took out X" |
| "I'm a Jew, Yamato" | "I'm with you, Yamato" |
| "Stun and Furnace" | "Stun Infernus" |
| "Stone [Character]" | "Stun [Character]" |
| "Starting Furnace" | "Stun Infernus" |
| "Done sinclair" | "Stun Sinclair" |
| "Dunraven" | "Stun Operative" / "Stun Raven" |
| "Don't fathom" | "Stun Fathom" |
| "Gun trapper" | "Stun Trapper" |
| "Darn Vyper" | "Stun Vyper" |
| "Startin' Warden" | "Stun Warden" |
| "Stand dynamo" | "Stun Dynamo" |
| "Quills on the roof" | "Krill's on the roof" |
| "Grills on a roof" | "Krill's on a roof" |
| "I saw race" | "I saw Wraith" |
| "Race on top of" | "Wraith's on top of" |
| "Just Business Race" | "Just business, Wraith" |
| "Castle Victory" | "Careful, Victor" |
| "Victory's almost back" | "Victor's almost back" |
| "Victory is dead" | "Victor is dead" |

### 5. Location/Context Errors

| Error | Correct |
|-------|---------|
| "on top of me" | "on top of mid" |
| "on the breach" | "on the bridge" |
| "under da garage" | "under the garage" |
| "Dormants in Mid" | "Doorman's in Mid" |
| "Slorks and Mid" | "Slork's in Mid" |
| "Minas on top of mid" | "Mina's on top of mid" |
| "Ravens in mid" | "Raven's in mid" |

### 6. Whisper Hallucinations

Whisper sometimes generates YouTube-style phrases that don't exist in the audio:

| Hallucination Examples |
|------------------------|
| "Thank you for watching!" |
| "Thanks for watching!" |
| "Please subscribe!" |
| "Like and subscribe!" |
| "If you found this helpful, please subscribe..." |
| "??" (placeholder for unrecognized audio) |

These typically appear at the end of short audio clips and should be removed or replaced.

## Prevention Tips for Whisper

### 1. Use Initial Prompt with Game Vocabulary

When using Whisper's API, provide an `initial_prompt` parameter with domain-specific terms:

```python
import whisper

model = whisper.load_model("large-v3")
result = model.transcribe(
    "audio.mp3",
    initial_prompt="Wraith, Doorman, Kelvin, Dynamo, Graf, Stun, Heal, Yamato, Fathom, Venator, Paradox, Sinclair, Paige, Holliday, Calico, Infernus, Vindicta, Bebop, McGinnis"
)
```

### 2. Use Larger Models

Larger Whisper models (large-v2, large-v3) have better accuracy for unusual terms.

### 3. Post-Process with the Auto-Fix Script

Run `autoFixWhisperErrors.py` after transcription to catch remaining errors:

```bash
# Dry run to see what would be changed
python3 autoFixWhisperErrors.py data --dry-run --verbose

# Apply the fixes
python3 autoFixWhisperErrors.py data --apply
```

### 4. Use Word-Level Timestamps

When using Whisper with `word_timestamps=True`, you can identify low-confidence words and flag them for manual review.

### 5. Create a Post-Processing Pipeline

1. Transcribe with Whisper (using initial_prompt)
2. Run `autoFixWhisperErrors.py`
3. Run `validate_json.py` to ensure JSON validity
4. Manually review flagged files if needed

## Script Usage

### `autoFixWhisperErrors.py`

```bash
# Show help
python3 autoFixWhisperErrors.py --help

# Dry run (see changes without modifying files)
python3 autoFixWhisperErrors.py data --dry-run

# Verbose dry run (see all changes)
python3 autoFixWhisperErrors.py data --dry-run --verbose

# Apply fixes
python3 autoFixWhisperErrors.py data --apply
```

### `validate_json.py`

```bash
# Validate all JSON files in the data directory
python3 validate_json.py
```

## Adding New Corrections

To add new corrections to `autoFixWhisperErrors.py`:

1. **Character Name Corrections**: Add to `CHARACTER_NAME_CORRECTIONS` dictionary
2. **Phrase Patterns**: Add to `PHRASE_CORRECTIONS` list as `(regex_pattern, replacement)` tuples

Example:
```python
# In CHARACTER_NAME_CORRECTIONS:
"NewError": "CorrectName",

# In PHRASE_CORRECTIONS:
(r"New Error Pattern\b", "Correct Pattern"),
```

## Files in This Repository

| File | Purpose |
|------|---------|
| `autoFixWhisperErrors.py` | Automatically fix common Whisper transcription errors |
| `validate_json.py` | Validate JSON file structure |
| `commonMistakeFix.py` | Original mistake fix script |
| `allCapsFix.py` | Fix all-caps transcription issues |

## Contributing

When you find new transcription errors:

1. Add the pattern to `autoFixWhisperErrors.py`
2. Test with `--dry-run` first
3. Run validation after applying changes
4. Submit a PR with the fix
