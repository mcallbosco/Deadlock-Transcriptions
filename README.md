# Deadlock-Transcriptions

![JSON Validation](https://github.com/mcallbosco/Deadlock-Transcriptions/workflows/Validate%20JSON%20Files/badge.svg)

Until subtitles are added, this is a repo to have transcriptions of deadlock voicelines. These are the transcriptions used on deadlock.mcallbos.co

# Format
The most up to date transcriptions are in main. Previous updates transcriptions are in a respective branch. For really old updates, it may be in the old-format branch.

All JSON files in the `data/` directory follow one of two standardized structures. See [VALIDATION.md](VALIDATION.md) for details on the expected JSON formats.

# Contribute
Feel free to contribute corrections. To find a file, press `t` or click the go to file bar in the repo and search for the file you want to edit. If you are coming from deadlock.mcallbos.co, the file name should be visible there. You can then click the marker and then create a PR. If you are editing multiple files, please consider making a fork based off of main, doing all your file edits in your fork, and then submitting a PR using the fork since that will allow all of your changes to be in one PR.

## JSON Validation
All JSON files are automatically validated for correctness. Before submitting a PR, you can run the validation locally:

```bash
python3 validate_json.py
```

See [VALIDATION.md](VALIDATION.md) for more information about the supported JSON structures and validation process. 
