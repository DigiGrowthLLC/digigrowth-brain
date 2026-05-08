# Add Managed Agent

Onboards a new agent so the EA can manage it — read its files, edit its config, and trigger runs — without leaving the EA chat session.

**Run this skill when Dylan adds a new agent and wants the EA to manage it.**

---

## What This Skill Does

1. Reads the new agent's directory to understand its structure
2. Adds the agent's directory to `additionalDirectories` in EA's `settings.json`
3. Creates a `manage-<agent-name>/SKILL.md` in the EA's skills folder
4. Creates a `CLAUDE.md` in the agent's directory as a file map
5. Logs the decision in `decisions/log.md`

---

## Instructions

Ask Dylan for the following before doing anything else:
- **Agent name** — short slug used for the skill folder name (e.g. `email-responder`, `report-builder`)
- **Agent directory** — full path on disk (e.g. `C:\Users\dylan\Videos\Business\AI Agents\Email Responder`)
- **One-line description** — what the agent does

Then execute these steps in order.

### Step 1 — Read the Agent's Directory

Read the agent's key files to understand:
- What files control its behavior (config, prompts, memory, etc.)
- How it's invoked (Python script? batch file? CLI?)
- What tools or APIs it uses
- What outputs it produces

If a `CLAUDE.md` already exists, read it. Otherwise you'll create one in Step 4.

### Step 2 — Update EA's settings.json

File: `C:\Users\dylan\Videos\Business\AI Agents\Executive Assistant\.claude\settings.json`

Add the agent's directory path to `permissions.additionalDirectories`. Merge with any existing entries — do not replace.

```json
{
  "permissions": {
    "additionalDirectories": [
      "...existing entries...",
      "C:\\path\\to\\new\\agent"
    ]
  }
}
```

### Step 3 — Create the Management Skill

Create `.claude/skills/manage-<agent-name>/SKILL.md` in the EA.

The skill file must contain:

```markdown
# Manage [Agent Name]

[One-line description of what the agent does]

**Agent location:** [full path]

---

## File Map

| File | What it controls |
|---|---|
| [file] | [purpose] |
...

---

## Run Commands

[How to trigger the agent — exact Bash/PowerShell command]

---

## Common Tasks

[Playbooks for the 3-5 most likely things Dylan will ask the EA to do with this agent]
- How to update its criteria or config
- How to check its last run status
- How to trigger a run

---

## Current Standing Directives

*Dylan updates this section to give ongoing orders to the EA about this agent.*

- [Sensible defaults based on what you learned about the agent]

---

## Notes

[Any security notes, gotchas, or important constraints]
```

Fill in every section based on what you read in Step 1. Do not leave placeholder text.

### Step 4 — Create CLAUDE.md in the Agent's Directory

If no `CLAUDE.md` exists, create one. Keep it minimal — it's a map, not instructions.

```markdown
# [Agent Name]

[One-line description]

**Managed by:** Dylan's Executive Assistant — see `.claude/skills/manage-<agent-name>/SKILL.md` in the `digigrowth-brain` repo
**Run via:** [how to run it]

## File Roles

| File | Purpose |
|---|---|
...

## Security

[List any files that must never be committed]
```

### Step 5 — Log the Decision

Append to `decisions/log.md`:

```
[YYYY-MM-DD] DECISION: Added [agent name] to EA management via additionalDirectories + skill file | REASONING: [why Dylan added this agent] | CONTEXT: [what it does, how it's invoked]
```

### Step 6 — Confirm

Tell Dylan:
- The skill was created at `.claude/skills/manage-<agent-name>/SKILL.md`
- The directory was added to `additionalDirectories`
- How to invoke the new management skill (e.g. "manage the email responder")
- Whether `python-dotenv` or any other dependency changes are needed
