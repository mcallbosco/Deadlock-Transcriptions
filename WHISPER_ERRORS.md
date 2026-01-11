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

### 1. Character Name Misrecognition

Whisper often struggles with unusual or game-specific names. Common patterns include:

| Original Name | Common Whisper Errors |
|---------------|----------------------|
| Wraith | Race, Raid, Rate, Rates, Raze |
| Doorman | Dormin, Dorman, Doman, Dolmen, Doughman, Tolman, Dormant, Dormands |
| Graf | Graph, Graphs, Grath, Grafton |
| Venator | Venera, Venetus, Betterless |
| Fathom | Fatum, Rathom, "Don't fathom" (for "Stun Fathom") |
| Haze | Hayes, Hace |
| Krill | Quill, Grill, Quills |
| Viscous | Viscus |
| Kelvin | Kelphin, Kermin |
| Sinclair | Clairborne, Clear |
| Paige | Spades |
| Ivy | Hyvie, Ivey |
| Operative | Raven (consistently misrecognized) |
| Victor | Victory, Fixers, Pictures |
| Calico | Talico, Gallico |
| Trapper | "Gun trapper" (for "Stun Trapper") |
| Vyper | "Darn Vyper" (for "Stun Vyper") |
| Seven | 7, Se7en |
| McGinnis | McInnes, McGuinness, Guinness |
| Grey Talon | Talon, Greytaran |
| Murphy | "Stan murphy" |

### 2. Action Word Errors

Gaming terms are often misrecognized:

| Correct | Common Errors |
|---------|---------------|
| Stun | Stone, Stan, Stand, Done, Don't, Dun, Gun, Darn, Startin' |
| Heal | Hear |

Note: "Stun X" is frequently misheard as "Stan X", "Stone X", "Done X", "Don't X", "Gun X", etc.

### 3. Homophone Confusions

| Correct Context | Error |
|-----------------|-------|
| "I can heal you" | "I can hear you" |
| "what X bought" | "what X brought" |
| "took out X" | "took our X" |
| "They took out" | "He/She/It took out" |

### 4. Phrase-Level Misrecognitions

| Incorrect | Correct |
|-----------|---------|
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
