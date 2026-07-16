#!/usr/bin/env bash
# SessionStart hook — sync shared Claude skills into ~/.claude/skills.
#
# ClaudeSkills-di-Tia is the single source of truth for custom skills.
# This hook works in two layouts, so the same file can be reused as-is:
#
#   1. Skills repo itself   -> skill folders live at the repo root.
#   2. Consumer project     -> skills repo is a submodule at
#                              .claude/skills-shared.
#
# In both cases every folder that contains a SKILL.md is copied into
# ~/.claude/skills, so a Claude Code session (local or on the web) can load
# the skills. Files that changed upstream are refreshed; files deleted
# upstream disappear (each managed skill is mirrored, not merely overlaid).
#
# Design goal (acceptance criterion): never fail in a blocking way. Every
# step is guarded and the hook always exits 0.

# --- Resolve the project directory -----------------------------------------
# CLAUDE_PROJECT_DIR is set by Claude Code; fall back to the git root or cwd
# so the hook is also runnable by hand for testing.
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-}"
if [ -z "$PROJECT_DIR" ]; then
  PROJECT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi

# --- Best-effort submodule checkout ----------------------------------------
# The cloud clone does not always initialise submodules. This is a no-op when
# there are none (e.g. when this repo is itself the skills source).
if [ -f "$PROJECT_DIR/.gitmodules" ]; then
  git -C "$PROJECT_DIR" submodule update --init --recursive >/dev/null 2>&1 || true
fi

SKILLS_DIR="$HOME/.claude/skills"
mkdir -p "$SKILLS_DIR" 2>/dev/null || true

# --- Locate skill folders and mirror them ----------------------------------
# Candidate source roots, in priority order. The first is the consumer layout
# (submodule), the second is this repo acting as the skills source.
CANDIDATES=(
  "$PROJECT_DIR/.claude/skills-shared"
  "$PROJECT_DIR"
)

synced=()
seen=" "
for root in "${CANDIDATES[@]}"; do
  [ -d "$root" ] || continue
  for skill in "$root"/*/; do
    [ -d "$skill" ] || continue
    [ -f "${skill}SKILL.md" ] || continue
    name="$(basename "$skill")"
    case "$name" in
      .*) continue ;;                       # skip dotfolders (.git, .claude, ...)
    esac
    case "$seen" in
      *" $name "*) continue ;;              # first candidate wins on duplicates
    esac
    seen="$seen$name "
    target="$SKILLS_DIR/$name"
    rm -rf "$target" 2>/dev/null || true
    if cp -r "$skill" "$target" 2>/dev/null; then
      synced+=("$name")
    fi
  done
done

# --- Emit a small, valid SessionStart context note -------------------------
count="${#synced[@]}"
if [ "$count" -gt 0 ]; then
  list="$(printf '%s, ' "${synced[@]}")"; list="${list%, }"
  msg="Synced $count shared skill(s) into ~/.claude/skills: $list. They load on the next skill scan."
else
  msg="Shared-skills sync ran; no skill folders found yet (add them to this repo)."
fi
# Strip characters that would break the JSON string (defensive; names are safe).
msg="${msg//\\/}"; msg="${msg//\"/}"

printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$msg"
exit 0
