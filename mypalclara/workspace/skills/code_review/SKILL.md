---
name: code_review
description: Review code for quality, security, and maintainability
---

## Code Review Instructions

When reviewing code, check:
1. Correctness: Does the code do what it claims?
2. Security: Are there injection risks, auth bypasses, or data leaks?
3. Performance: Are there obvious inefficiencies?
4. Maintainability: Is the code clear and well-structured?
5. Testing: Are edge cases covered?

## Output Format

Provide findings as a structured list:
- **Critical**: Issues that must be fixed before merge
- **Warning**: Issues that should be addressed but aren't blockers
- **Suggestion**: Improvements that would be nice to have
- **Praise**: Things done well (reinforces good patterns)

Be specific: reference line numbers, variable names, and concrete alternatives.
