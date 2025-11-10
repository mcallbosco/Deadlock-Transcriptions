#!/usr/bin/env python3
"""
JSON Structure Validator for Deadlock Transcriptions

This script validates that all JSON files in the data directory follow one of the 
expected structures for the Deadlock-Transcriptions repository.

Supported structures:
1. Voiceline: Contains voiceline_id, timestamp, segments
2. Simple file: Contains file, segments
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any


def is_valid_voiceline(data: Dict) -> Tuple[bool, str]:
    """
    Validates a voiceline JSON structure.
    
    Expected structure:
    {
        "voiceline_id": string,
        "timestamp": string,
        "segments": [
            {
                "start": number,
                "end": number,
                "text": string,
                "part": number
            }
        ]
    }
    """
    if "voiceline_id" not in data:
        return False, "Missing 'voiceline_id' field"
    
    if not isinstance(data["voiceline_id"], str):
        return False, "'voiceline_id' must be a string"
    
    if "timestamp" not in data:
        return False, "Missing 'timestamp' field"
    
    if not isinstance(data["timestamp"], str):
        return False, "'timestamp' must be a string"
    
    if "segments" not in data:
        return False, "Missing 'segments' field"
    
    if not isinstance(data["segments"], list):
        return False, "'segments' must be a list"
    
    for idx, segment in enumerate(data["segments"]):
        if not isinstance(segment, dict):
            return False, f"Segment {idx} must be a dictionary"
        
        required_fields = ["start", "end", "text", "part"]
        for field in required_fields:
            if field not in segment:
                return False, f"Segment {idx} missing required field '{field}'"
        
        if not isinstance(segment["start"], (int, float)):
            return False, f"Segment {idx} 'start' must be a number"
        
        if not isinstance(segment["end"], (int, float)):
            return False, f"Segment {idx} 'end' must be a number"
        
        if not isinstance(segment["text"], str):
            return False, f"Segment {idx} 'text' must be a string"
        
        if not isinstance(segment["part"], int):
            return False, f"Segment {idx} 'part' must be an integer"
    
    return True, "Valid voiceline structure"


def is_valid_simple_file(data: Dict) -> Tuple[bool, str]:
    """
    Validates a simple file JSON structure.
    
    Expected structure:
    {
        "file": string,
        "segments": [
            {
                "start": number,
                "end": number,
                "text": string
            }
        ]
    }
    """
    if "file" not in data:
        return False, "Missing 'file' field"
    
    if not isinstance(data["file"], str):
        return False, "'file' must be a string"
    
    if "segments" not in data:
        return False, "Missing 'segments' field"
    
    if not isinstance(data["segments"], list):
        return False, "'segments' must be a list"
    
    for idx, segment in enumerate(data["segments"]):
        if not isinstance(segment, dict):
            return False, f"Segment {idx} must be a dictionary"
        
        required_fields = ["start", "end", "text"]
        for field in required_fields:
            if field not in segment:
                return False, f"Segment {idx} missing required field '{field}'"
        
        if not isinstance(segment["start"], (int, float)):
            return False, f"Segment {idx} 'start' must be a number"
        
        if not isinstance(segment["end"], (int, float)):
            return False, f"Segment {idx} 'end' must be a number"
        
        if not isinstance(segment["text"], str):
            return False, f"Segment {idx} 'text' must be a string"
    
    return True, "Valid simple file structure"


def validate_json_file(file_path: Path) -> Tuple[bool, str]:
    """
    Validates a single JSON file against all known structures.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {str(e)}"
    except Exception as e:
        return False, f"Error reading file: {str(e)}"
    
    if not isinstance(data, dict):
        return False, "JSON root must be an object"
    
    # Try each structure type
    # Check for voiceline structure
    if "voiceline_id" in data:
        return is_valid_voiceline(data)
    
    # Check for simple file structure
    if "file" in data:
        return is_valid_simple_file(data)
    
    return False, "Unknown JSON structure - does not match any expected format"


def validate_all_json_files(data_dir: Path) -> Tuple[int, int, List[Tuple[str, str]]]:
    """
    Validates all JSON files in the data directory.
    
    Returns:
        Tuple of (total_files, valid_files, errors)
        where errors is a list of (filename, error_message) tuples
    """
    if not data_dir.exists():
        print(f"Error: Directory {data_dir} does not exist")
        return 0, 0, []
    
    json_files = list(data_dir.glob("*.json"))
    total_files = len(json_files)
    valid_files = 0
    errors = []
    
    print(f"Validating {total_files} JSON files in {data_dir}...")
    
    for json_file in json_files:
        is_valid, message = validate_json_file(json_file)
        if is_valid:
            valid_files += 1
        else:
            errors.append((json_file.name, message))
    
    return total_files, valid_files, errors


def main():
    """Main function to run validation."""
    # Find the data directory relative to this script
    script_dir = Path(__file__).parent
    data_dir = script_dir / "data"
    
    # Allow override via command line argument
    if len(sys.argv) > 1:
        data_dir = Path(sys.argv[1])
    
    total, valid, errors = validate_all_json_files(data_dir)
    
    print(f"\n{'='*60}")
    print(f"Validation Results:")
    print(f"{'='*60}")
    print(f"Total files: {total}")
    print(f"Valid files: {valid}")
    print(f"Invalid files: {len(errors)}")
    print(f"{'='*60}")
    
    if errors:
        print("\nErrors found:")
        print(f"{'='*60}")
        for filename, error in errors:
            print(f"\n{filename}:")
            print(f"  {error}")
        print(f"\n{'='*60}")
        sys.exit(1)
    else:
        print("\n✓ All JSON files are valid!")
        sys.exit(0)


if __name__ == "__main__":
    main()
