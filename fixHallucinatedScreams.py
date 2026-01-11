#!/usr/bin/env python3
"""
Fix hallucinated Whisper transcriptions for screams and groans.

Whisper often hallucinates random text for non-verbal sounds like screams, 
groans, and grunts in pain/effort audio files. This script identifies and 
clears those hallucinated transcriptions.

Files targeted:
- *_pain_* files (except low_health_warning which may have actual dialogue)
- *_effort_* files

Common hallucinations include:
- "Thank you for watching!"
- "Subscribe to my channel"
- URLs and website references
- "Do not include extra whitespace..."
- Random numbers and punctuation only
- Non-English text and gibberish
- YouTube-style CTAs
"""

import os
import re
import json
import argparse
from pathlib import Path


# File patterns that contain non-verbal sounds (screams/groans)
NONVERBAL_FILE_PATTERNS = [
    r'_pain_big_',
    r'_pain_small_',
    r'_pain_death_',
    r'_pain_akira_laser_',
    r'_effort_',
]

# Patterns that indicate hallucinated text (these should be cleared)
# Using case-insensitive matching
HALLUCINATION_PATTERNS = [
    # YouTube/social media CTAs
    r'thank\s*(you|u)\s*(for)?\s*watching',
    r'thanks\s*(for)?\s*watching',
    r'subscri(be|b|ption)',
    r'like.*comment.*subscri',
    r'don\'?t\s*forget\s*to',
    r'leave\s*a\s*comment',
    r'next\s*video',
    r'previous\s*video',
    r'see\s*you\s*in\s*the',
    r'hope\s*you\s*enjoy',
    r'enjoy\s*the\s*video',
    r'click\s*(on|the|here)',
    r'notification',
    r'channel',
    r'patreon',
    r'please\s*like',
    r'link\s*in\s*(the)?\s*description',
    
    # Transcription service artifacts
    r'transcription\s*(by|is|has|service)',
    r'translation\s*(by|is)',
    r'subs?\s*by',
    r'subtitle',
    r'casting\s*words',
    r'do\s*not\s*include\s*extra\s*whitespace',
    r'ambiguous\s*transcription',
    r'transcription\s*sting',
    
    # Website/URL references
    r'http[s]?://',
    r'www\.',
    r'\.com',
    r'\.co\.uk',
    r'\.org',
    r'\.net',
    r'\.au',
    r'sites\.google',
    r'youtube',
    r'tinyurl',
    r'slidespot',
    r'pissedconsumer',
    
    # Copyright/legal text
    r'©',
    r'copyright',
    r'all\s*rights\s*reserved',
    r'trademark',
    r'disney',
    r'all\s*characters.*fictitious',
    r'disclaimer',
    r'used\s*by\s*permission',
    
    # Generic filler phrases that don't make sense for screams
    r'to\s*be\s*continued',
    r'the\s*end\.?$',
    r'^game\s*over$',
    r'first\s*person\s*videos?',
    r'chapter\s*\d',
    r'episode\s*\d',
    r'part\s*\d',
    r'^available\s*(now|at|for)',
    
    # Random text/gibberish patterns
    r'[а-яА-Я]{3,}',  # Cyrillic text
    r'[ㄱ-ㅎ가-힣]{2,}',  # Korean text (except for simple exclamations)
    r'[ぁ-んァ-ン]{3,}',  # Japanese hiragana/katakana
    r'[一-龥]{2,}',  # Chinese characters
    r'éhéhé',  # Repeated diacritical nonsense
    r'🅱|🅰|🅵|🆂|🆁|🆃|🅷|🅴|🅶|🅳|🅿',  # Block emoji
    r'[►◄▲▼]{2,}',  # Arrow symbols
    
    # Instructional/meta text
    r'if\s*you\s*(find|have|did|enjoyed)',
    r'please\s*(see|click|post|leave)',
    r'questions?\s*(or|and)?\s*(comments?|problems?)',
    r'comments?\s*section',
    r'classroom\s*footage',
    r'save\s*it\s*in\s*your',
    
    # Specific hallucinations found in data
    r'horse\s*neighs',
    r'teenage\s*girl\s*screams',
    r'awkward\s*silence',
    r'scream\s*song',
    r'u\.?s\.?\s*money\s*reserve',
    r'rhyme\s*films',
    r'bloopers?',
    r'off\s*camera',
    r'available.*free',
    r'weltwerk',
    r'behaviour',
    r'answers?\s*this\s*question',
    r'perfect\s*for\s*that\s*purpose',
    r'keep\s*the\s*video',
    r'children\'?s\s*charity',
    r'amogus',
    r'control$',
    r'^grunt$',
    r'^cough$',
    r'\*\*?(burp|fart|yawn|sigh|groan|grunt|shiver)\*\*?',
    r'\(\*(burp|fart|yawn|sigh|groan|grunt|shiver|horse)\*\)',
]

# Patterns that indicate valid screams/groans (should be kept)
VALID_SCREAM_PATTERNS = [
    r'^[AaUuOoEe]+[HhGgRr]*[!\.]*$',  # Ahhh!, Ugh!, etc.
    r'^(G|D\'?)?[AaUuOo]+[HhGgRr]*[!\.]*$',  # Gah!, Doh!, etc.
    r'^[Hh]+[IiYyAaUu]+[AaHh]*[!\.]*$',  # Hyah!, Hiyah!, etc.
    r'^(Ny|N)[AaEeUu]+[Hh]*[!\.]*$',  # Nyeh!, Nah!, etc.
    r'^[Oo]+[FfOo]+[!\.]*$',  # Oof!, Off!
    r'^[Bb]+[AaLlRrUu]+[GgHhRr]*[!\.]*$',  # Bah!, Blah!, Blargh!, Bruh!
    r'^[Rr]+[AaOo]+[Ww]*[Rr]*[!\.]*$',  # Rawr!, Roar!
    r'^[Mm]+[Ww]*[Aa]+[Hh]*[!\.]*$',  # Mwah!
    r'^[Hh]+[Mm]+[Pp]*[Hh]*[Ff]*[!\.]*$',  # Hmph!, Hmpf!, Hmm
    r'^[Yy]+[Ee]*[Aa]+[Hh]*[!\.]*$',  # Yeah!, Yah!
    r'^[Nn]+[Oo]+[!\.]*$',  # No!, Nooo!
    r'^[Oo]+[Ww]+[!\.]*$',  # Ow!
    r'^[Hh]+[Uu]+[Hh]*[!\.]*$',  # Huh!
    r'^[Ss]+[Ee]+[Ee]*[Yy]*[Aa]*[!\.]*$',  # See ya!
    r'^[Bb]+[Oo]+[Oo]*[Ff]*[!\.]*$',  # Boof!, Boo!
    r'^[Gg]+[Rr]+[Rr]*[!\.]*$',  # GRR!
]


def is_hallucinated(text):
    """Check if the text appears to be a Whisper hallucination."""
    if not text:
        return False
    
    # Strip whitespace for analysis
    text = text.strip()
    
    if not text:
        return False
    
    # Check if it's a valid scream/groan pattern first
    for pattern in VALID_SCREAM_PATTERNS:
        if re.match(pattern, text, re.IGNORECASE):
            return False
    
    # Check for hallucination patterns
    for pattern in HALLUCINATION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    # Check for single punctuation/numbers only (likely hallucinations)
    if re.match(r'^[\s\d\.,\?\!\-\/\~\•\=]+$', text):
        return True
    
    # Check for very long text (screams shouldn't be sentences)
    if len(text.split()) > 5:
        return True
    
    return False


def should_process_file(filename):
    """Check if this file should be processed (contains non-verbal sounds)."""
    for pattern in NONVERBAL_FILE_PATTERNS:
        if re.search(pattern, filename):
            return True
    return False


def process_json_file(filepath, dry_run=True):
    """Process a single JSON file and clear hallucinated transcriptions."""
    changes = []
    
    if not should_process_file(filepath.name):
        return changes
    
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
                if is_hallucinated(original):
                    changes.append({
                        'file': str(filepath),
                        'original': original,
                        'fixed': ''
                    })
                    segment['text'] = ''
                    modified = True
    
    if modified and not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
    
    return changes


def process_directory(directory, dry_run=True, verbose=False):
    """Process all JSON files in a directory."""
    all_changes = []
    
    data_dir = Path(directory)
    json_files = list(data_dir.glob('*.json'))
    
    # Filter to only files that match our patterns
    target_files = [f for f in json_files if should_process_file(f.name)]
    
    print(f"Processing {len(target_files)} scream/groan files (out of {len(json_files)} total)...")
    
    for filepath in target_files:
        changes = process_json_file(filepath, dry_run)
        all_changes.extend(changes)
        
        if verbose and changes:
            for change in changes:
                print(f"\n{filepath.name}:")
                print(f"  - {repr(change['original'])}")
                print(f"  + (cleared)")
    
    return all_changes


def main():
    parser = argparse.ArgumentParser(
        description='Fix hallucinated Whisper transcriptions in scream/groan files'
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
    print(f"Total hallucinated transcriptions found: {len(changes)}")
    
    if dry_run:
        print("\nThis was a DRY RUN. No files were modified.")
        print("Run with --apply to actually clear the hallucinated transcriptions.")
    else:
        print(f"\n{len(changes)} transcriptions cleared.")
    
    # Show summary
    if changes:
        print(f"\nSample changes (showing up to 20):")
        for change in changes[:20]:
            filename = Path(change['file']).name
            orig = change['original'][:60] + '...' if len(change['original']) > 60 else change['original']
            print(f"  {filename}: {repr(orig)} -> (cleared)")


if __name__ == '__main__':
    main()
