# Test-Esami-Unimerc

## Skill condivise

Le skill custom vivono nel submodule `.claude/skills-shared` (repo
[ClaudeSkills-di-Tia](https://github.com/Matthewuwu/ClaudeSkills-di-Tia),
branch `claude/skill-infrastructure-setup-plxxep`) e vengono sincronizzate in
`~/.claude/skills` da un hook `SessionStart`.

- **Aggiornarle** (prendere le versioni più recenti dal repo condiviso):
  `git submodule update --remote .claude/skills-shared` → commit → push.
- **Pubblicare una skill creata/modificata qui**:
  `.claude/skills-shared/scripts/export-new-skills.sh`.
