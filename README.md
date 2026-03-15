# Agent Skills Marketplace

A community skills marketplace for Claude Code. Browse and install skills to extend Claude Code with new capabilities.

## Usage

### Add this marketplace

```
/plugin marketplace add <repo-url>
```

### Browse available skills

```
/plugin marketplace search <query>
```

### Install a skill

```
/plugin install <skill-name>
```

## Contributing a skill

Each skill lives in its own directory under `skills/`:

```
skills/
└── your-skill/
    ├── .claude-plugin/
    │   └── plugin.json
    └── skills/
        └── your-skill/
            └── SKILL.md
```

### SKILL.md format

Skills use the [Agent Skills spec](https://agentskills.io/specification) with YAML frontmatter:

```markdown
---
name: your-skill
description: Short description of what the skill does
version: 1.0.0
---

# Your Skill

Instructions for Claude Code when this skill is activated.
```

### plugin.json

Each skill needs a `.claude-plugin/plugin.json` that describes the plugin:

```json
{
  "name": "your-skill",
  "description": "What your skill does",
  "version": "1.0.0",
  "skills": [
    {
      "name": "your-skill",
      "path": "skills/your-skill/SKILL.md"
    }
  ]
}
```

### Steps to contribute

1. Fork this repo
2. Create your skill directory under `skills/`
3. Add your `SKILL.md` and `plugin.json`
4. Submit a pull request
