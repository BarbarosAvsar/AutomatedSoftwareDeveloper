# Bugfix Playbook

Use this playbook for every reproducible bug fix.

1. **Capture a failing repro**
   - Add a focused failing test, or a minimal reproduction script.
   - Keep inputs deterministic and avoid network calls.
2. **Fix the root cause**
   - Implement the smallest safe change that resolves the failure.
   - Maintain backward compatibility for `autosd run`.
3. **Add regression coverage**
   - Ensure the new or updated test now passes.
   - Add conformance fixtures if generated projects are affected.
4. **Update documentation**
   - Add a changelog note describing the fix.
   - Update operational docs if behavior or usage changes.
5. **Run quality gates**
   - `python -m ruff check .`
   - `python -m mypy automated_software_developer`
   - `python -m pytest`

Never claim perfect security or zero bugs; rely on automated gates to block regressions.
