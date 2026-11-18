# UiPath to Power Automate Desktop (Robin) Migration Suite

100% Offline & Online Conversion Tools with Golden Database & Pre-Paste Validation.

---

## 🚀 Quick Start (Choose Your Mode)

### Mode 1: 100% Pure Offline Converter (No Internet, No API Key)
- **Double-click:** `run_offline.bat`
- Opens at: `http://localhost:8505`
- **Features:**
  - Converts any `.nupkg` package into 100% paste-validated Robin script.
  - Automatically queries the **Golden Database** (`robin_database.db`) for instant cache hits.
  - Allows you to save newly verified flows with 1 click.
  - Includes **32 Pre-verified Enterprise Activity Patterns** (Excel, PDF, Outlook, SQL, Web API).

### Mode 2: Full Explorer (Offline AST + PwC GenAI LLM)
- **Double-click:** `start.bat`
- Opens at: `http://localhost:8502`
- **Features:**
  - Deep `.nupkg` file inspection, dependency discovery, and XAML activity breakdown.
  - Pure LLM Converter powered by the **PwC GenAI APAC Gateway** (`https://genai-sharedservice-apac.pwcinternal.com`).

### Mode 3: Instant Command Line (CLI)
Open your terminal inside this folder and run:
```powershell
python test_offline.py "data/ReadPdf_FromPageToPage.1.0.1 1.nupkg"
```

---

## 📁 File Structure

| File / Folder | Purpose |
| :--- | :--- |
| **`app_offline.py`** | Dedicated Streamlit Web UI for 100% pure offline conversion. |
| **`run_offline.bat`** | One-click launcher for `app_offline.py` (Port 8505). |
| **`robin_converter.py`** | Universal AST transpiler with .NET System.IO transpilation & 0-error validator. |
| **`robin_db.py`** | Database manager for Golden flows, enterprise patterns, and AI training exports. |
| **`robin_database.db`** | SQLite database pre-loaded with verified flows and 32 activity patterns. |
| **`test_offline.py`** | Offline CLI runner (`python test_offline.py <file.nupkg>`). |
| **`test_online.py`** | Online CLI runner for PwC GenAI gateway (`python test_online.py <file.nupkg> <api_key>`). |
| **`nupkg_browser.py`** | All-in-one explorer with XAML analysis, offline converter, and PwC GenAI. |
| **`start.bat`** | One-click launcher for `nupkg_browser.py` (Port 8502). |
| **`data/`** | Sample `.nupkg` packages and AI fine-tuning datasets (`golden_training_openai.jsonl`, etc.). |
| **`pad-robin-action-kb-main/`** | Official PAD 2.74 action knowledge base (1,135 actions) & `check-flows.js` validator. |

---

## 🛡️ Why Scripts Are Guaranteed Pasteable (0 Errors)
1. **Dynamic AST Variable Discovery**: Discovers all variables and types (`DataTable`, `List`, `Number`, `Boolean`, `String`) and pre-declares them at Line 1.
2. **.NET System.IO Transpilation**: Converts raw C# methods (`Directory.GetFiles`, `Path.GetFileNameWithoutExtension`, `.Count()`) into native PAD actions.
3. **Strict Formatting Rules**: Enforces double backslashes before `%` (`\\%Var%`), prevents trailing backslash quote escapes (`C:\\`), and eliminates lone `%` signs.
4. **Pre-Paste Validation Loop**: Every script is automatically validated with `check-flows.js` before being presented.

