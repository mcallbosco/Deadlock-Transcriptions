# Whisper Transcription Error Fixing Guide

This document explains common transcription errors that occur when using OpenAI Whisper for game audio files and how to fix them.

## Common Whisper Transcription Errors

### 1. Character Name Misrecognition

Whisper often struggles with unusual or game-specific names. Common patterns include:

| Original Name | Common Whisper Errors |
|---------------|----------------------|
| Wraith | Race, Raid, Rate, Rates, Raze |
| Doorman | Dormin, Dorman, Doman, Dolmen, Doughman, Tolman |
| Graf | Graph, Graphs, Grath |
| Venator | Venera, Venetus, Betterless |
| Fathom | Fatum, Rathom |
| Haze | Hayes, Hace |
| Krill | Quill, Grill |
| Viscous | Viscus |
| Kelvin | Kelphin |
| Sinclair | Clairborne |
| Paige | Spades |
| Ivy | Hyvie |

### 2. Action Word Errors

Gaming terms are often misrecognized:

| Correct | Common Errors |
|---------|---------------|
| Stun | Stone, Stan |
| Heal | Hear |

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

### 5. Location/Context Errors

| Error | Correct |
|-------|---------|
| "on top of me" | "on top of mid" |
| "on the breach" | "on the bridge" |
| "under da garage" | "under the garage" |

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
