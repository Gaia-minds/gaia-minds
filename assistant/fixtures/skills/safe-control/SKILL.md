---
name: safe-control
description: Deterministic safe control fixture used by the quality matrix.
capabilities:
  - file_read
---

Use only deterministic read-only repository checks.
Do not execute shell scripts, write files, or access remote endpoints.
