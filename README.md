# my-claude-skills

Claude Code skills for session memory and recall with Obsidian integration. Adapted from [ArtemXTech/personal-os-skills](https://github.com/ArtemXTech/personal-os-skills).

## Skills

### sync-claude-sessions

Export Claude Code conversations to Obsidian markdown with live sync via hooks. Auto-syncs on every prompt submission and response completion.

Features:
- Real-time session sync to `Claude-Sessions/` in your Obsidian vault
- Frontmatter with metadata (date, title, skills, messages, status, tags, rating)
- Korean + English keyword extraction for tags (via ir's Korean preprocessor)
- `## My Notes` section preserved across syncs
- Commands: `sync`, `export`, `resume`, `note`, `close`, `list`, `log`

### recall

Load context from previous sessions. Three modes:

- **Temporal** (date-based): `/recall yesterday`, `/recall last week`
- **Topic** (BM25 search): `/recall authentication`, `/recall 인증 작업` (requires [ir](https://github.com/vlwkaos/ir))
- **Graph** (visualization): `/recall graph last week` (requires networkx, pyvis)

Ends every recall with **One Thing** — the single highest-leverage next action.

### save-doc

Save session content (analysis, specs, designs) to Obsidian vault.

## Installation

### Option A: Claude Code Plugin (recommended)

```bash
claude plugin marketplace add blackironj/my-claude-skills
claude plugin install my-claude-skills
```

### Option B: Manual

```bash
git clone https://github.com/blackironj/my-claude-skills.git
cd my-claude-skills

# Install skills
cp -r skills/recall ~/.claude/skills/
cp -r skills/sync-claude-sessions ~/.claude/skills/
cp -r skills/save-doc ~/.claude/skills/

# Install SessionEnd hook
mkdir -p ~/.claude/hooks
cp hooks/index-sessions.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/index-sessions.sh
```

## Configuration

### 1. Create `~/.claude/env` (per machine)

```bash
cat > ~/.claude/env << 'EOF'
# Claude Code environment — sourced by all hooks
# Change this per machine
export VAULT_DIR="/path/to/your/obsidian-vault"
EOF
```

This is the only file that differs per PC. All hooks source it automatically.

### 2. Add hooks to `~/.claude/settings.json`

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": ". ~/.claude/env && python ~/.claude/skills/sync-claude-sessions/scripts/claude-sessions sync",
            "timeout": 10
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": ". ~/.claude/env && python ~/.claude/skills/sync-claude-sessions/scripts/claude-sessions sync",
            "timeout": 10
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/index-sessions.sh >> ~/.claude/hooks/index-sessions.log 2>&1",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### 3. (Optional) ir for topic search

```bash
# Build ir from source (Rust 1.80+ required, libclang-dev, cmake)
cd ~/workspace
git clone https://github.com/vlwkaos/ir.git && cd ir
cargo install --path . --no-default-features --features llama-openmp  # Linux
# cargo install --path .  # macOS (Metal auto-detected)

# Korean preprocessor
cd preprocessors/ko/lindera-tokenize  # Linux: build from source
cargo install --path .
ir preprocessor add ko lindera-tokenize
# macOS: ir preprocessor install ko

# Register collections and build index
ir collection add sessions "$VAULT_DIR/Claude-Sessions/"
ir collection add notes "$VAULT_DIR/Notes/"
ir preprocessor bind ko sessions
ir preprocessor bind ko notes
ir update
```

ir is installed per machine. The Obsidian vault syncs across PCs; ir index is local.

See [setup guide](skills/sync-claude-sessions/workflows/setup.md) for full details.

## Updating

### Plugin install
```bash
claude plugin update my-claude-skills
```

### Manual install
```bash
cd my-claude-skills
cp -r skills/recall ~/.claude/skills/
cp -r skills/sync-claude-sessions ~/.claude/skills/
cp hooks/index-sessions.sh ~/.claude/hooks/
```

## Requirements

- Python 3.10+
- Claude Code with hooks support
- Obsidian vault
- (Optional) [ir](https://github.com/vlwkaos/ir) + Rust 1.80+ for topic search
- (Optional) networkx + pyvis for graph visualization

## License

MIT
