# Add Source (grow the knowledge base)

Use when Dylan says "add this video/book/PDF to my mindset coach", or downloads a new
mindset/self-improvement video and asks to learn from it.

## Steps
1. **Get the text.** For a video in ~/Downloads (newest first: `ls -t ~/Downloads/*.mp4`), run
   `python content-agent/tools/transcribe.py <file>` from the repo root (faster-whisper; long videos
   take several minutes, so run it in the background). Copy the transcript to
   `knowledge/transcripts/<author>-<topic>.txt`. For a PDF, extract its text; image-only PDFs need
   page rendering.
2. **Read all of it** before writing anything.
3. **Write `knowledge/<author>-<topic>.md`:** source + date at the top, core line, then every
   framework, definition, model, named study, quote and action step, organized by section. Be
   thorough: Dylan wants as much relevant detail as possible. Note where it overlaps or conflicts
   with the existing knowledge files.
4. **List it** in CLAUDE.md under "Knowledge base" with a one-line summary.
5. **Apply it to Dylan:** pull out its action steps and either walk him through them (one at a
   time, his answers) or add them as pending items to memory.md. Fold anything personal he shares
   into context/.
6. Add a dated line to memory.md.
