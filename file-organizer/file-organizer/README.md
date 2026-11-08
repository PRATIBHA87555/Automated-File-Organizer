# File Organizer

A desktop app that sorts a messy folder (like Downloads) into category folders:
Images, Videos, Audio, Documents, Spreadsheets, Presentations, Archives, Code, Installers, Others.

## Setup
    pip install -r requirements.txt
    python app.py

(On Linux you may also need: `sudo apt install python3-tk`)

## How to use
1. Pick a folder (defaults to Downloads) with **Browse**.
2. **Preview** shows what would move, nothing is touched yet.
3. **Organize Now** moves the files.
4. **Undo Last** puts the last batch back exactly where it was.
5. **Auto-organize** switch: re-checks the folder every 10 seconds.

## Safety
- Only files directly in the folder are moved (subfolders are left alone).
- Files still downloading (.crdownload, .part, .tmp) or modified in the last 2 seconds are skipped.
- Name clashes never overwrite: `photo.jpg` becomes `photo (1).jpg`.
- Undo history is stored in `.organizer_history.json` inside the folder.

## Tests
    python test_organizer.py
