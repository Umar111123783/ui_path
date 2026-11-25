# Universal UiPath-to-PAD Conversion Engine
> Automated migration of enterprise UiPath automation packages into Microsoft Power Automate Desktop 2.74 Classic Robin flows.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Target Platform](https://img.shields.io/badge/Target-PAD%202.74%20Classic%20Robin-green)](https://learn.microsoft.com/en-us/power-automate/desktop-flows/)
[![Validation](https://img.shields.io/badge/Syntax%20Validation-0%20Errors%20(check--flows.js)-brightgreen)](pad-robin-action-kb-main/marketing/video/tools/check-flows.js)
[![License](https://img.shields.io/badge/Architecture-7--Stage%20IR%20Compiler-orange)](HANDOVER_DOCUMENTATION.md)

---

## 📖 Team Handover Documentation
For the complete technical architecture, file map, syntax rules, developer guide, and handover checklist, see:
👉 **[HANDOVER_DOCUMENTATION.md](HANDOVER_DOCUMENTATION.md)**

---

## 🚀 Quick Start

### 1. Command Line Interface (CLI)
Convert any UiPath package (`.zip`, `.nupkg`, folder, or `.xaml`):
```powershell
python convert.py "data/SourcingBot.zip"
```
Generated artifacts are placed in `Conversion_Output/`:
* `Conversion_Output/Main_Robin_Script.txt` (1-Click Paste for PAD Main tab)
* `Conversion_Output/Reports/Conversion_Report.html` (Visual audit report)
* `Conversion_Output/Subflows/*.robin` (Individual subflows)

### 2. Streamlit Web UI
Launch the interactive web portal:
```powershell
streamlit run app_offline.py
```
Open `http://localhost:8501` to drag and drop packages, inspect flows, and download conversion bundles.

### 3. Run Regression Test Suite
Run automated verification across 5 real-world enterprise packages:
```powershell
python tests/test_universal_engine.py
```

---

## 🏗️ 7-Stage Decoupled IR Architecture

1. **Stage 1 — Project Discovery (`scanner/project_scanner.py`):** Recursive extraction, `project.json` parsing, workflow inventory.
2. **Stage 2 — XAML Intelligence (`parsers/xaml_parser.py`, `parsers/expression_parser.py`):** Schema-aware XML parsing, AST extraction, expression transpilation.
3. **Stage 3 — Auto-Detect Complexity (`analyzer/complexity_analyzer.py`):** 7-dimension scoring (`SIMPLE`, `INTERMEDIATE`, `ADVANCED`, `ENTERPRISE`) & Blueprint detection.
4. **Stage 4 — Dependency Graph & IR (`scanner/workflow_graph.py`, `ir/`):** Invocation hierarchy, topological sort, cycle detection.
5. **Stage 5 — Conversion Registry & Flattener (`converters/workflow_flattener.py`, `robin_converter.py`):** Inlines subflows into sequential `**REGION` blocks on the Main tab.
6. **Stage 6 — Native Robin PAD 2.74 Generation:** Clean variable initializations, single quote escaping, paired `%` interpolations.
7. **Stage 7 — Strict Validation (`validators/strict_validator.py`):** Balance checks & official Microsoft `check-flows.js` execution (0 errors required).

---

## 📁 Repository Overview

* `convert.py` — Master CLI runner.
* `app_offline.py` — Streamlit web application.
* `core/` — Master pipeline coordinator (`conversion_engine.py`), context, and project models.
* `scanner/` — Project and workflow graph scanners.
* `parsers/` — XAML XML parser and VB.NET / C# expression transpiler.
* `analyzer/` — 7-dimension complexity scoring and scaffold detection.
* `converters/` — Single Main flattener and activity converters.
* `validators/` — Strict control-flow validator and `check-flows.js` runner.
* `generators/` — HTML and Markdown audit report generators.
* `pad-robin-action-kb-main/` — Microsoft ActionKB (1,135 actions) and `check-flows.js`.
* `tests/` — Automated test suite verifying 5 enterprise packages.
