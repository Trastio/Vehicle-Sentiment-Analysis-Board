#!/bin/bash
rm -f ".claude/settings.local.json" 2>/dev/null
rm -rf docs/superpowers 2>/dev/null
rm -rf docs/plans 2>/dev/null
rm -rf docs/brainstorming 2>/dev/null
rm -f "docs/改造方案.md" 2>/dev/null
find docs -name "*.md" -exec grep -l "86183" {} \; 2>/dev/null | while read f; do rm -f "$f"; done
