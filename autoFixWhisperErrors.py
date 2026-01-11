#!/usr/bin/env python3
"""
Automatic Whisper Transcription Error Fixer

This script fixes common errors that occur when using OpenAI Whisper for 
transcription of Deadlock game audio files. Whisper often misrecognizes:
- Character names (especially unusual/game-specific names)
- Action words in gaming context ("Stun" becomes "Stone", etc.)
- Homophones ("heal" vs "hear", "bought" vs "brought")
- Proper noun capitalization

WHISPER PREVENTION TIPS:
1. Use Whisper's `initial_prompt` parameter with character names and game terms
   Example: initial_prompt="Wraith, Doorman, Kelvin, Dynamo, Graf, Stun, Heal, Yamato"
2. Consider using larger Whisper models (large-v3) for better accuracy
3. Post-process with this script to catch remaining errors
4. Use Whisper's word-level timestamps to identify low-confidence words
5. Create a custom vocabulary list for domain-specific terms

Common error patterns fixed by this script:
- Character name variations (Wraith: Race, Raid, Rate, Raze, etc.)
- Action word misrecognitions (Stun: Stan, Stone, etc.)
- Homophone confusions (heal/hear, bought/brought, out/our)
- Missing capitalization for proper nouns
- Common phrase patterns (e.g., "Care for X" → "Careful, X")
"""

import os
import re
import json
import argparse
from pathlib import Path


# Character name corrections - maps common Whisper mistakes to correct names
# These are ordered by specificity (more specific patterns first)
# NOTE: Only include clear errors, not context-dependent words
CHARACTER_NAME_CORRECTIONS = {
    # Doorman variations
    "Dormin": "Doorman",
    "Dorman": "Doorman",
    "Doman": "Doorman",
    "Dolmen": "Doorman",
    "Doughman": "Doorman",
    "Tolman": "Doorman",
    
    # Graf variations  
    "Grath": "Graf",
    
    # Venator (priest) variations
    "Venera": "Venator",
    "Venetus": "Venator",
    "Betterless": "Venator",
    
    # Haze variations (only clear errors)
    "Hayes": "Haze",
    "Hace": "Haze",
    
    # Krill variations (only clear errors)
    "Quill": "Krill",
    
    # Fathom (slork) variations
    "Fatum": "Fathom",
    "Rathom": "Fathom",
    
    # Sinclair (magician) variations
    "Clairborne": "Sinclair",
    
    # Page/Paige (bookworm) variations
    "Spades": "Paige",
    
    # Ivy (tengu) variations
    "Hyvie": "Ivy",
    
    # Warden variations
    "Wargon": "Warden",
    
    # Viscous variations
    "Viscus": "Viscous",
    
    # Kelvin variations
    "Kelphin": "Kelvin",
}

# Action word corrections - context-sensitive
ACTION_CORRECTIONS = {
    # Stun variations - "Stone X" or "Stan X" should be "Stun X"
    "Stone": "Stun",
    "Stan": "Stun",
    "Stamina": "Stun Mina",
    "Stanyamato": "Stun Yamato",
    "Stormwrecker": "Stun Wrecker",
    "Stonewraith": "Stun Wraith",
    "Sunwraith": "Stun Wraith",
    
    # Heal/hear confusions in "can heal you" context
    # These are handled by phrase patterns below
}

# Phrase pattern corrections - (pattern, replacement)
# IMPORTANT: Only include patterns that are clearly errors based on context
# These are high-confidence fixes based on PRs #65 and #67
PHRASE_CORRECTIONS = [
    # "can hear you" → "can heal you" in healing context (ping_can_heal files)
    (r'I can hear you\b', 'I can heal you'),
    (r'I can hear ya\b', 'I can heal ya'),
    
    # "took our/your X" → "took out X" in kill announcements
    (r'\btook our\b', 'took out'),
    (r'\btook your\b', 'took out'),
    
    # "He/She/It took out" → "They took out" for consistency
    (r'\bHe took out\b', 'They took out'),
    (r'\bShe took out\b', 'They took out'),
    (r'\bIt took out\b', 'They took out'),
    
    # "Let's talk about" → "They took out" (common misrecognition in kill context)
    (r"Let's talk about\b", "They took out"),
    
    # "forgot the" → "took out the" in kill context
    (r'They forgot the\b', 'They took out the'),
    
    # Specific severe misrecognitions
    (r"I'm a Jew, Yamato\b", "I'm with you, Yamato"),
    (r"How would you, Bebop\b", "I'm with you, Bebop"),
    
    # "Assault X" → "I saw X" (common misrecognition in saw context)
    (r'\bAssault\b', 'I saw'),
    
    # "A siggraph" → "I see Graf"
    (r'A siggraph\b', 'I see Graf'),
    
    # "Decode Seven" → "They killed Seven"
    (r'Decode Seven\b', 'They killed Seven'),
    
    # "And took out" → "They took out"
    (r'\bAnd took out\b', 'They took out'),
    
    # "brought" → "bought" in item check context 
    (r'what (\w+) brought\b', r'what \1 bought'),
    
    # Specific bot pattern corrections
    (r"Check out our PageBot\b", "Check out what Paige bought"),
    (r"Check out McGinnis' board\b", "Check out what McGinnis bought"),
    (r"Check out what's 7-Ball\b", "Check out what Seven bought"),
    (r"Check out what's in Clairborne\b", "Check out what Sinclair bought"),
    (r"Check out Krillbot\b", "Check out what Krill bought"),
    (r"Check out Aminabot\b", "Check out what Mina bought"),
    (r"Check out what I re-bought\b", "Check out what Ivy bought"),
    (r"Check out WarWraith Bar\b", "Check out what Wraith bought"),
    
    # "Let's take our" → "Let's take out" (attack context)
    (r"Let's take our graph\b", "Let's take out Graf"),
    (r"Let's take our Graf\b", "Let's take out Graf"),
    
    # Stun corrections - Stone/Stan → Stun
    (r"Stone Viscous\b", "Stun Viscous"),
    (r"Stone viscous\b", "Stun Viscous"),
    (r"Stone Page\b", "Stun Paige"),
    (r"Stone Dynamo\b", "Stun Dynamo"),
    (r"Stone Geist\b", "Stun Geist"),
    (r"Stone Abrams\b", "Stun Abrams"),
    (r"Stone Mirage\b", "Stun Mirage"),
    (r"Stone Grey Talon\b", "Stun Grey Talon"),
    (r"Stone Grey Calon\b", "Stun Grey Talon"),
    (r"Stone Shiv\b", "Stun Shiv"),
    (r"Stone Cadence\b", "Stun Cadence"),
    (r"Stone Paradox\b", "Stun Paradox"),
    (r"Stone Krill\b", "Stun Krill"),
    (r"Stone callie\b", "Stun Calico"),
    (r"Stone Kelvin\b", "Stun Kelvin"),
    (r"Stone raven\b", "Stun Raven"),
    (r"Stone Raven\b", "Stun Raven"),
    (r"Stone Gallico\b", "Stun Calico"),
    (r"Stone the Guinness\b", "Stun McGinnis"),
    (r"Stone wraith\b", "Stun Wraith"),
    (r"Stone Wraith\b", "Stun Wraith"),
    (r"Stone Ivy\b", "Stun Ivy"),
    (r"Stone ivy\b", "Stun Ivy"),
    (r"Stone pocket\b", "Stun Pocket"),
    (r"Stone Pocket\b", "Stun Pocket"),
    (r"Stone Vyper\b", "Stun Vyper"),
    (r"Stone the Hyvie\b", "Stun Ivy"),
    (r"Stone Vindicta\b", "Stun Vindicta"),
    (r"Stone Fathom\b", "Stun Fathom"),
    (r"Stone Lash\b", "Stun Lash"),
    (r"Stone Lush\b", "Stun Lash"),
    (r"Stone Bebop\b", "Stun Bebop"),
    (r"Stone the record\b", "Stun Wrecker"),
    (r"Stone yamato\b", "Stun Yamato"),
    (r"Stone Yamato\b", "Stun Yamato"),
    (r"Stone victor\b", "Stun Victor"),
    (r"Stan Viscous\b", "Stun Viscous"),
    (r"Stan busy\b", "Stun Billy"),
    (r"Stan Seven\b", "Stun Seven"),
    
    # Stamina → Stun Mina  
    (r"\bStamina\b", "Stun Mina"),
    
    # Compound word errors
    (r"Stanyamato\b", "Stun Yamato"),
    (r"Stormwrecker\b", "Stun Wrecker"),
    (r"Stonewraith\b", "Stun Wraith"),
    (r"Sunwraith\b", "Stun Wraith"),
    
    # Stun name variations
    (r"Stun and Furnace\b", "Stun Infernus"),
    (r"Stun in furnace\b", "Stun Infernus"),
    (r"Stun in Furnace\b", "Stun Infernus"),
    (r"Stun your eyes\b", "Stun Mirage"),
    (r"Stun great talent\b", "Stun Grey Talon"),
    (r"Stun great talon\b", "Stun Grey Talon"),
    (r"Stun holiday\b", "Stun Holliday"),
    (r"Stun Holiday\b", "Stun Holliday"),
    (r"Stun the witch\b", "Stun Titania"),
    (r"Stun killed\b", "Stun Kelvin"),
    (r"Stun grill\b", "Stun Krill"),
    (r"Stun recker\b", "Stun Wrecker"),
    (r"Stun quill\b", "Stun Krill"),
    (r"Stun dorman\b", "Stun Doorman"),
    (r"Stun hayes\b", "Stun Haze"),
    (r"Stun taco\b", "Stun Calico"),
    (r"Stun meta\b", "Stun Mina"),
    (r"\bStun Raid\b", "Stun Wraith"),
    (r"\bStun race\b", "Stun Wraith"),
    (r"\bStun Race\b", "Stun Wraith"),
    
    # Ignore Wraith variations
    (r"\bIgnore Raid\b", "Ignore Wraith"),
    (r"\bIgnore race\b", "Ignore Wraith"),
    
    # "under da garage" → "under the garage"
    (r"under da garage\b", "under the garage"),
    
    # "on the breach" → "on the bridge"
    (r"on the breach\b", "on the bridge"),
    
    # Specific Wraith misrecognitions from PR #67
    (r"Rates on mid\b", "Wraith's in mid"),
    (r"Rates on top of mid\b", "Wraith's on top of mid"),
    (r"Rates on top o' the garage\b", "Wraith's on top of the garage"),
    (r"Rates under the garage\b", "Wraith's under the garage"),
    (r"Rate is missing\b", "Wraith is missing"),
    (r"Race in mid\b", "Wraith's in mid"),
    (r"Race under the garage\b", "Wraith's under the garage"),
    (r"Raids on the roof\b", "Wraith's on the roof"),
    
    # Graf fixes
    (r"Graphs missing\b", "Graf's missing"),
    (r"Graphs Missing\b", "Graf's Missing"),
    (r"I see Grath\b", "I see Graf"),
    (r"Careful Graph\b", "Careful, Graf"),
    
    # Doorman variations
    (r"Dorman's on top of the garage\b", "Doorman's on top of the garage"),
    (r"The Dormant on top of Mid\b", "The Doorman's on top of Mid"),
    (r"Torments Under the Garage\b", "Doorman's under the Garage"),
    (r"The Dormin's dead\b", "The Doorman's dead"),
    (r"The Dormin was here\b", "The Doorman was here"),
    (r"The Dormin is almost back\b", "The Doorman is almost back"),
    (r"The Dorman's in Mid\b", "The Doorman's in Mid"),
    (r"The Doman's on the bridge\b", "The Doorman's on the bridge"),
    (r"The Doughman's on the Roof\b", "The Doorman's on the Roof"),
    (r"Check out what the Dolmen bought\b", "Check out what the Doorman bought"),
    (r"Ignore the Dolmen\b", "Ignore the Doorman"),
    (r"Stun Dolmen\b", "Stun Doorman"),
    (r"I'm with you, Dorman\b", "I'm with you, Doorman"),
    (r"Careful, Dorman\b", "Careful, Doorman"),
    
    # Venator fixes from PR #65
    (r"Venera was here\b", "Venator was here"),
    (r"Venera's on the bridge\b", "Venator's on the bridge"),
    (r"Venetus under da garage\b", "Venator's under the garage"),
    (r"Banners in mid\b", "Venator's in mid"),
    (r"Betterless on top of mid\b", "Venator's on top of mid"),
    (r"Stun veneta\b", "Stun Venator"),
    (r"I saw venera\b", "I saw Venator"),
    (r"Careful, fella\b", "Careful, Venator"),
    
    # Calico fixes
    (r"Catacombs on top of mid\b", "Calico's on top of mid"),
    
    # Ivy fixes
    (r"Dive is on top of mid\b", "Ivy's on top of mid"),
    
    # Billy fixes  
    (r"It is on top of the garage\b", "Billy's on top of the garage"),
    (r"It is on top of mid\b", "Billy's on top of mid"),
    (r"It is under the garage\b", "Billy's under the garage"),
    (r"It is on the bridge\b", "Billy's on the bridge"),
    (r"Pillies on the roof\b", "Billy's on the roof"),
    
    # Fathom fixes
    (r"Fatum's on top of mid\b", "Fathom's on top of mid"),
    
    # Victor fixes from PR #65
    (r"Victus on top of mid\b", "Victor's on top of mid"),
]

# Lowercase character names that should be capitalized when they appear alone
# NOTE: Only apply in specific contexts to avoid false positives
CAPITALIZE_NAMES = []  # Disabled for now - too many false positives


def fix_text(text, filename=""):
    """Apply all corrections to a text string."""
    original = text
    
    # Apply phrase corrections first (order matters)
    for pattern, replacement in PHRASE_CORRECTIONS:
        text = re.sub(pattern, replacement, text)
    
    # Apply character name corrections
    for wrong, correct in CHARACTER_NAME_CORRECTIONS.items():
        # Word boundary matching to avoid partial replacements
        pattern = r'\b' + re.escape(wrong) + r'\b'
        text = re.sub(pattern, correct, text, flags=re.IGNORECASE)
    
    return text


def process_json_file(filepath, dry_run=True):
    """Process a single JSON file and apply fixes."""
    changes = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"Error reading {filepath}: {e}")
        return changes
    
    modified = False
    
    if 'segments' in data:
        for segment in data['segments']:
            if 'text' in segment:
                original = segment['text']
                fixed = fix_text(original, filepath.name)
                if original != fixed:
                    changes.append({
                        'file': str(filepath),
                        'original': original,
                        'fixed': fixed
                    })
                    segment['text'] = fixed
                    modified = True
    
    if modified and not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')  # Add trailing newline
    
    return changes


def process_directory(directory, dry_run=True, verbose=False):
    """Process all JSON files in a directory."""
    all_changes = []
    
    data_dir = Path(directory)
    json_files = list(data_dir.glob('*.json'))
    
    print(f"Processing {len(json_files)} JSON files...")
    
    for filepath in json_files:
        changes = process_json_file(filepath, dry_run)
        all_changes.extend(changes)
        
        if verbose and changes:
            for change in changes:
                print(f"\n{filepath.name}:")
                print(f"  - {change['original']}")
                print(f"  + {change['fixed']}")
    
    return all_changes


def main():
    parser = argparse.ArgumentParser(
        description='Fix common Whisper transcription errors in JSON files'
    )
    parser.add_argument(
        'directory',
        nargs='?',
        default='data',
        help='Directory containing JSON files (default: data)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Show changes without modifying files (default: True)'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Actually apply the changes to files'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output for each change'
    )
    
    args = parser.parse_args()
    
    dry_run = not args.apply
    
    changes = process_directory(args.directory, dry_run=dry_run, verbose=args.verbose)
    
    print(f"\n{'=' * 60}")
    print(f"Total changes: {len(changes)}")
    
    if dry_run:
        print("\nThis was a DRY RUN. No files were modified.")
        print("Run with --apply to actually make the changes.")
    else:
        print(f"\n{len(changes)} changes applied to files.")
    
    # Show summary of most common fixes
    if changes:
        print(f"\nSample changes (showing up to 10):")
        for change in changes[:10]:
            filename = Path(change['file']).name
            print(f"\n  {filename}:")
            print(f"    - {change['original']}")
            print(f"    + {change['fixed']}")


if __name__ == '__main__':
    main()
