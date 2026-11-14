# AI usage log

This project is developed with the assistance of a generative AI coding tool.
This file records what was generated, with which tool and model, so that the
use of AI can be disclosed accurately in publications. The author reviews the
generated material and is responsible for all content of the repository. The AI
tool is not an author.

| Date | Tool | What was generated |
|---|---|---|
| 2026-11-11 | Claude Code (Anthropic), models claude-opus-5-5 and claude-fable-5-2 | Independent re-check of the SPEC.md section 5 validation values and the truncated-Gaussian A_eff formula. |
| 2026-11-11 | Claude Code (Anthropic), model claude-fable-5-2 | First version of the whole repository: `src/beamforge/` (beam models, energy/fluence, uncertainty, measured profile, calculator, setup-file loader, CLI), `tests/`, `examples/reference_setup.toml`, `README.md`, `pyproject.toml`. Formulas come from SPEC.md and the references cited in the docstrings; design choices not fixed by SPEC.md were reviewed and accepted by the author on 2026-11-11. Code read by the author on 2026-11-11. |
| 2026-11-11 | Claude Code (Anthropic), model claude-fable-5-2 | Renamed the package from the placeholder `laserspot` to `beamforge`; added licence and repository metadata to `pyproject.toml`. |
| 2026-11-12 | Claude Code (Anthropic), model claude-fable-5-2 | Desktop interface `src/beamforge/gui/` (PySide6 and pyqtgraph), its tests `tests/test_gui.py`, the Windows build scripts in `packaging/`, the setup-file writer and `sample_profile` helper, and the README section on the desktop application. The interface contains no physics; it calls the library. Not yet reviewed line by line by the author. |
| 2026-11-12 | Claude Code (Anthropic), model claude-fable-5-2 | Start-up screen `src/beamforge/gui/splash.py` (logo, tag line, animated loading bar), its test, and `packaging/make_splash.py`. The tag line was written by the author. Not yet reviewed line by line by the author. |
| 2026-11-14 | Claude Code (Anthropic), model claude-fable-5-2 | Two changes to the desktop interface requested by the author: removed the scanning inputs from the window (the library and command line keep them), and fixed drop-down lists that were unreadable when Windows is in dark mode. |
