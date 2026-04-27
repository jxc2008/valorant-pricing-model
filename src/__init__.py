"""Valorant live pricing model — top-level package.

See CLAUDE.md and prd.md for design intent. The single canonical pricing entry
point is `src.pricing.live_theo.live_theo` (DEC-010). The single source-of-truth
for thresholds and magic numbers is `src.config.constants` (DEC-016 / CLAUDE.md
rule 12).
"""
