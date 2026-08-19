"""
Retired. The Google Places API + Anthropic Batches API pipeline this file
used to run got too expensive to justify at current lead volume.

Replaced by the `scrape-leads` Claude Code skill (.claude/skills/scrape-leads/
SKILL.md), which drives Google Maps directly via the Playwright MCP browser
tools and does qualification/grading/opener-writing as Claude Code reasoning
instead of a metered API call — same rules (role.txt/memory.txt/prompt.txt,
unchanged), $0 marginal cost beyond the existing Claude subscription.

The free helper functions this file used to contain (website scraping, owner
extraction, progress tracking, OS push) now live in lib.py, importable or
callable via its CLI — see lib.py's docstring.

Run the pipeline with: a Claude Code session invoking the scrape-leads skill
(manually, via /loop, or via Windows Task Scheduler — see leadgen-agent/CLAUDE.md).
"""

if __name__ == "__main__":
    print(__doc__)
