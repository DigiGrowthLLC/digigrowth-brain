# Transcribe Skill

Transcribe a video or audio file and optionally extract key insights into a reference file.

---

## Trigger

Any message containing a video/audio filename (`.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`, `.m4v`, `.mp3`, `.m4a`) or the word "transcribe".

---

## Mode 1: Transcribe Only

**Use when:** Dylan pastes a filename or says "transcribe [file]" without asking for notes or insights.

**Steps:**
1. Extract the filename from Dylan's message
2. Run from the `content-agent/` directory:
   ```
   python tools/transcribe.py "[filename]"
   ```
3. The script auto-searches Downloads if the file isn't in the current dir
4. Wait for completion — it prints each line as it transcribes so Dylan can see progress
5. Report the output path when done

**Output:** `outputs/transcript-[filename]-YYYY-MM-DD.txt`

---

## Mode 2: Transcribe + Extract Insights

**Use when:** Dylan says "transcribe and extract", "transcribe and save notes", "transcribe and add to reference", or asks to save insights after transcription.

**Steps:**
1. Run transcription (same as Mode 1)
2. Read the saved transcript file
3. Identify the core topic of the video
4. Extract structured knowledge following the `context/brand-strategy.md` format:
   - Clear section headers
   - Bullet points for rules/principles
   - Named frameworks with their components
   - No filler — only actionable, reusable knowledge
5. Save to `context/[topic]-notes.md`
6. Confirm both files saved

---

## After Transcribing

1. Report: "Transcript saved to `outputs/transcript-[name].txt`"
2. Ask: "Want me to extract key insights into a reference file?"
3. If yes → switch to Mode 2 using the already-saved transcript (no re-run needed)
