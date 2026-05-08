# Subagent & Skill Creation

Reference and best practices for creating Claude Code subagents and skills correctly.

---

## Skills vs Subagents — Pick the Right Tool

| | Skills | Subagents |
|---|---|---|
| **Location** | `.claude/skills/<name>/SKILL.md` | `.claude/agents/<name>.md` |
| **Runs in** | Main conversation context | Isolated context (own window) |
| **Returns** | Works inline | Summary only |
| **Use when** | Reusable prompt/workflow, needs back-and-forth | Task produces verbose output, needs tool restrictions, parallel work |

**Rule of thumb:** If the task would flood the main context with logs, search results, or file contents — use a subagent. If it's a repeatable workflow that benefits from full context — use a skill.

---

## Skill File Structure

```
.claude/skills/
  skill-name/
    SKILL.md       ← instructions, runs in main conversation
```

Plain Markdown. No frontmatter required. The file is the prompt — write clear, step-by-step instructions.

---

## Subagent File Structure

```
.claude/agents/
  agent-name.md   ← project-level (version controlled)

~/.claude/agents/
  agent-name.md   ← user-level (all projects)
```

Uses YAML frontmatter + Markdown system prompt:

```markdown
---
name: my-agent
description: When Claude should delegate to this agent — be specific, Claude reads this to decide
tools: Read, Grep, Glob, Bash
model: haiku
permissionMode: default
memory: project
---

System prompt here.
```

---

## Frontmatter Fields

Only `name` and `description` are required. Everything else is optional.

| Field | Values | Notes |
|---|---|---|
| `name` | lowercase + hyphens | Unique identifier |
| `description` | string | **Most important field** — Claude uses this to decide when to delegate. Be specific. |
| `tools` | `Read, Grep, Glob, Bash, ...` | Allowlist — omit to inherit all tools |
| `disallowedTools` | `Write, Edit, ...` | Denylist — inherit everything except these |
| `model` | `haiku` / `sonnet` / `opus` / full model ID / `inherit` | Defaults to `inherit` |
| `permissionMode` | `default` / `acceptEdits` / `auto` / `dontAsk` / `bypassPermissions` / `plan` | |
| `memory` | `user` / `project` / `local` | Enables persistent memory across sessions |
| `mcpServers` | list of server names or inline definitions | Scopes MCP to this agent only |
| `skills` | list of skill names | Preloads full skill content into agent context at startup |
| `isolation` | `worktree` | Runs agent in isolated git worktree |
| `background` | `true` / `false` | Always run as background task |
| `color` | `red` / `blue` / `green` / `yellow` / `purple` / `orange` / `pink` / `cyan` | UI display color |
| `maxTurns` | number | Max agentic turns before stopping |

---

## Model Selection

- `haiku` — fast, cheap. Use for read-only / search agents (Explore pattern)
- `sonnet` — balanced capability and speed. Default for most agents
- `opus` — complex reasoning. Use sparingly for high-stakes tasks
- `inherit` — uses same model as main conversation (default when omitted)

---

## Tool Control

```yaml
# Allowlist — only these tools
tools: Read, Grep, Glob, Bash

# Denylist — inherit everything except these
disallowedTools: Write, Edit

# Restrict which subagents this agent can spawn
tools: Agent(worker, researcher), Read, Bash

# Allow spawning any subagent without restriction
tools: Agent, Read, Bash
```

If both `tools` and `disallowedTools` are set: denylist applied first, then allowlist resolved against what remains.

---

## Persistent Memory

```yaml
memory: project   # .claude/agent-memory/<name>/ — project-specific, shareable via git (recommended default)
memory: user      # ~/.claude/agent-memory/<name>/ — across all projects
memory: local     # .claude/agent-memory-local/<name>/ — project-specific, NOT in git
```

When enabled:
- Agent gets a persistent directory + `MEMORY.md`
- First 200 lines of `MEMORY.md` are injected into agent context at startup
- Include memory instructions in the system prompt so it proactively maintains its own knowledge base

---

## Scoping MCP Servers to a Subagent

```yaml
mcpServers:
  - Gmail                     # string reference — reuses already-configured server
  - playwright:               # inline definition — only this subagent gets it
      type: stdio
      command: npx
      args: ["-y", "@playwright/mcp@latest"]
```

**Why this matters:** Inline definitions keep MCP tools out of the main conversation's tool list entirely, reducing noise and context consumption.

---

## Permission Modes

- `bypassPermissions` — skips ALL prompts. Use with caution — only for trusted, well-scoped agents.
- `acceptEdits` — auto-accepts file edits in working directory
- `auto` — background classifier reviews commands
- `dontAsk` — auto-denies permission prompts (explicitly allowed tools still work)
- `plan` — read-only exploration only

**Note:** If the parent session uses `bypassPermissions` or `acceptEdits`, it takes precedence and the subagent cannot override it.

---

## Priority Order (highest wins when names conflict)

1. Managed settings (org-wide)
2. `--agents` CLI flag (current session only)
3. `.claude/agents/` (project level)
4. `~/.claude/agents/` (user level)
5. Plugin `agents/` directory

---

## Key Constraints

- Subagents **cannot spawn other subagents** (no nesting)
- Subagents start in the main conversation's working directory
- `cd` commands in Bash do not persist between tool calls within a subagent
- Minimum scheduled interval via `/schedule` is 1 hour
- Plugin subagents cannot use `hooks`, `mcpServers`, or `permissionMode`
- New subagent files require a session restart to load (or use `/agents` to load immediately)

---

## Preloading Skills into a Subagent

```yaml
skills:
  - daily-briefing
  - email-triage
```

Injects the full skill content into the subagent's context at startup. The subagent doesn't need to discover or load the skill — it already has it. Subagents do **not** inherit skills from the parent conversation; list them explicitly.
