---
name: squash-prep
description: Use when preparing commit stack for squash into PR
---

Analyze the commit stack for PR preparation:

1. Show commits since main:
   ```
   git log main..HEAD --oneline
   ```

2. Show overall diff stats:
   ```
   git diff main --stat
   ```

3. Summarize:
   - Number of commits to squash
   - Files changed
   - Key changes (look at commit messages)

4. Suggest a PR commit message following the format:
   ```
   <Short summary>

   <Description of what changed and why>

   Changes:
   - Bullet points
   ```
