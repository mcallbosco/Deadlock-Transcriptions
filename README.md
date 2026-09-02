# Deadlock Transcripts

Transcripts and content configuration used to generate VLViewer data.

Audio transcripts are stored below `transcripts/` at paths that mirror the audio files.
Each schema-v3 revision shares one subtitle across an array of audio SHA-256 values.
Grouping ignores case, Unicode punctuation, and whitespace; stored text is selected by
source authority (`official`, then `manual`, then `generated`).

Edit a revision's `text`, set `source` to `manual`, remove `model`, preview locally,
then commit. Split a hash into a separate revision when one recording needs different text.
