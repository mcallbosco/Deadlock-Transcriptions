# JSON Validation

This repository includes automated validation for all JSON files in the `data/` directory to ensure they follow the expected structure.

## Supported JSON Structures

The validator recognizes two types of JSON structures:

### 1. Voiceline Structure
Used for individual character voicelines.

```json
{
  "voiceline_id": "string",
  "timestamp": "string",
  "segments": [
    {
      "start": number,
      "end": number,
      "text": "string",
      "part": number
    }
  ]
}
```

### 2. Simple File Structure
Used for basic transcription files.

```json
{
  "file": "string",
  "segments": [
    {
      "start": number,
      "end": number,
      "text": "string"
    }
  ]
}
```

## Running Validation Locally

To validate all JSON files in the `data/` directory:

```bash
python3 validate_json.py
```

To validate JSON files in a different directory:

```bash
python3 validate_json.py /path/to/data/directory
```

## CI/CD Integration

The validation runs automatically on:
- Every push to the `main` or `master` branch that modifies JSON files
- Every pull request that modifies JSON files

The workflow will fail if any JSON file:
- Is not valid JSON
- Does not match one of the three expected structures
- Has missing required fields
- Has fields with incorrect data types

## Contributing

When adding or modifying JSON files, make sure to:
1. Follow one of the three supported structures above
2. Ensure all required fields are present
3. Use the correct data types for all fields
4. Run `python3 validate_json.py` locally before submitting a PR

If the validation fails in CI, the error message will indicate which file(s) have issues and what needs to be fixed.
