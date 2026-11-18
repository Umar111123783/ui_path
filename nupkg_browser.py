import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
import requests
import streamlit as st

from robin_converter import xaml_to_robin, generate_template_robin, validate_robin
from llm import DEFAULT_MODEL_NAME, convert_to_robin as llm_convert_to_robin, is_local_endpoint
from parser import (
    extract_zip,
    build_xml_context,
    get_dll_files,
    get_xaml_files,
    get_important_files,
    get_project_tree,
)

PWC_ENDPOINT = "https://genai-sharedservice-apac.pwcinternal.com/chat/completions"
PWC_MODELS = [
    "openai.global.gpt-4.1",
    "openai.global.gpt-4o",
    "openai.global.gpt-4o-mini",
    "azure.gpt-4o",
    "Custom..."
]

def fetch_available_models(endpoint: str, api_key: str):
    """Query gateway /v1/models endpoint to list available models for this key."""
    if not endpoint.strip() or not api_key.strip():
        return []
    base = endpoint.split("/chat/completions")[0].rstrip("/")
    for path in ["/v1/models", "/models"]:
        try:
            resp = requests.get(
                f"{base}{path}",
                headers={"API-Key": api_key.strip(), "accept": "application/json"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                models = [
                    m.get("id") or m.get("model")
                    for m in data.get("data", [])
                    if isinstance(m, dict) and (m.get("id") or m.get("model"))
                ]
                if models:
                    return sorted(models)
        except Exception:
            pass
    return []

st.set_page_config(
    page_title="NUPKG Explorer & PAD Robin LLM Converter",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0284c7;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 0.95rem;
        color: #64748b;
        margin-bottom: 1.2rem;
    }
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 12px;
    }
    .badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        background-color: #e0f2fe;
        color: #0369a1;
        margin-right: 6px;
    }
</style>
""", unsafe_allow_html=True)


def compress_xaml_for_speed(xaml_content: str) -> str:
    """Strip visual layout designer bloat to speed up LLM generation."""
    cleaned = re.sub(r'<sap:WorkflowViewStateService\.ViewState>.*?</sap:WorkflowViewStateService\.ViewState>', '', xaml_content, flags=re.DOTALL)
    cleaned = re.sub(r'<sap2010:WorkflowViewState\.IdRef>.*?</sap2010:WorkflowViewState\.IdRef>', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'\s*sap2010:WorkflowViewState\.IdRef="[^"]*"', '', cleaned)
    cleaned = re.sub(r'\s*sap:VirtualizedContainerService\.HintSize="[^"]*"', '', cleaned)
    cleaned = re.sub(r'\s*mc:Ignorable="[^"]*"', '', cleaned)
    cleaned = re.sub(r'\n\s*\n', '\n', cleaned)
    return cleaned


def parse_nuspec(xml_content):
    """Parse .nuspec XML file into structured dictionary."""
    metadata = {}
    try:
        root = ET.fromstring(xml_content)
        for elem in root.iter():
            if "}" in elem.tag:
                elem.tag = elem.tag.split("}", 1)[1]

        meta_elem = root.find("metadata")
        if meta_elem is not None:
            for child in meta_elem:
                if child.tag == "dependencies":
                    deps = []
                    for group in child.findall("group"):
                        tfm = group.get("targetFramework", "All")
                        for dep in group.findall("dependency"):
                            deps.append({
                                "id": dep.get("id", ""),
                                "version": dep.get("version", ""),
                                "targetFramework": tfm
                            })
                    for dep in child.findall("dependency"):
                        deps.append({
                            "id": dep.get("id", ""),
                            "version": dep.get("version", ""),
                            "targetFramework": "All"
                        })
                    metadata["dependencies"] = deps
                elif len(child) == 0:
                    metadata[child.tag] = child.text
    except Exception as e:
        metadata["_parse_error"] = str(e)
    return metadata


def parse_xaml_activities(xaml_content):
    """Extract workflow activities and variables from XAML."""
    activities = []
    variables = []
    arguments = []
    try:
        root = ET.fromstring(xaml_content)
        for elem in root.iter():
            tag = elem.tag.split("}")[1] if "}" in elem.tag else elem.tag
            if tag.startswith("x:Property"):
                arguments.append({
                    "name": elem.get("Name", "unnamed"),
                    "type": elem.get("Type", "Object"),
                    "direction": "In/Out"
                })
            elif tag == "Variable":
                variables.append({
                    "name": elem.get("Name", "unnamed"),
                    "type": elem.get("{http://schemas.microsoft.com/winfx/2006/xaml}TypeArguments", "Object")
                })
            elif not tag.startswith("x:") and not tag.startswith("scg:") and tag not in [
                "Activity", "VisualBasicValue", "VisualBasicReference", "Members",
                "TextExpression.NamespacesForImplementation", "TextExpression.ReferencesForImplementation",
                "Sequence", "Flowchart", "StateMachine"
            ]:
                disp_name = elem.get("DisplayName", tag)
                activities.append({
                    "type": tag,
                    "display_name": disp_name
                })
    except Exception:
        pass
    return activities, variables, arguments


# Session state defaults for LLM
if "llm_endpoint" not in st.session_state:
    st.session_state["llm_endpoint"] = PWC_ENDPOINT
if "llm_model" not in st.session_state:
    st.session_state["llm_model"] = os.environ.get("LLM_MODEL", DEFAULT_MODEL_NAME)
if "llm_api_key" not in st.session_state:
    st.session_state["llm_api_key"] = os.environ.get("LLM_API_KEY", "")


# --- SIDEBAR: Source Selection ---
st.sidebar.title("📦 NUPKG & LLM")
mode = st.sidebar.radio("Choose Source:", ["📂 Browse Local Directory", "📤 Upload .nupkg / .zip File"])

active_nupkg = None
pkg_bytes = None
pkg_filename = ""
extracted_folder_path = None

if mode == "📂 Browse Local Directory":
    default_dir = str(Path.home() / "Downloads")
    search_dir = st.sidebar.text_input("Folder Path:", value=default_dir)
    
    if os.path.exists(search_dir):
        try:
            nupkg_files = [f for f in os.listdir(search_dir) if f.lower().endswith(".nupkg") or f.lower().endswith(".zip")]
            if nupkg_files:
                selected_file = st.sidebar.selectbox("Select package:", nupkg_files)
                full_path = os.path.join(search_dir, selected_file)
                pkg_filename = selected_file
                try:
                    with open(full_path, "rb") as f:
                        pkg_bytes = f.read()
                    active_nupkg = zipfile.ZipFile(io.BytesIO(pkg_bytes))
                    extracted_folder_path = extract_zip(io.BytesIO(pkg_bytes))
                except Exception as e:
                    st.sidebar.error(f"Error opening package: {e}")
            else:
                st.sidebar.warning(f"No .nupkg or .zip files found in {search_dir}")
        except Exception as e:
            st.sidebar.error(f"Cannot read directory: {e}")
    else:
        st.sidebar.error("Directory does not exist.")

else:
    uploaded = st.sidebar.file_uploader("Upload .nupkg or .zip package", type=["nupkg", "zip"])
    if uploaded:
        pkg_filename = uploaded.name
        pkg_bytes = uploaded.read()
        try:
            active_nupkg = zipfile.ZipFile(io.BytesIO(pkg_bytes))
            uploaded.seek(0)
            extracted_folder_path = extract_zip(uploaded)
        except Exception as e:
            st.sidebar.error(f"Invalid package file: {e}")


# --- MAIN AREA ---
if not active_nupkg:
    st.markdown('<div class="main-header">🧠 UiPath → PAD Robin Converter & NUPKG Explorer</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Convert UiPath RPA projects to native Microsoft Power Automate Desktop (Robin) scripts via Pure LLM Engine (app_llm) or offline rule converter.</div>', unsafe_allow_html=True)
    
    st.info("👈 Please select a `.nupkg` package or upload a `.zip`/`.nupkg` file in the sidebar to get started.")

    # Generator Standalone Section
    st.subheader("🪄 Generate Power Automate Desktop (Robin) Scripts (Offline Recipes)")
    t_col1, t_col2 = st.columns([1, 2])
    with t_col1:
        recipe = st.selectbox(
            "Select Automation Recipe:",
            [
                ("folder_backup", "📁 Folder Backup (Downloads to Backup)"),
                ("excel_report", "📊 Excel Invoice Data & Summary Report"),
                ("outlook_attachments", "📧 Outlook Email & Attachment Extractor"),
                ("input_and_decision", "❓ Interactive Input Dialog & Decision"),
                ("sales_api_report", "🌐 REST API Request & Error Handling")
            ],
            format_func=lambda x: x[1]
        )
        if st.button("⚡ Generate Robin Script", type="primary"):
            st.session_state["standalone_robin"] = generate_template_robin(recipe[0])

    with t_col2:
        if "standalone_robin" in st.session_state:
            gen_code = st.session_state["standalone_robin"]
            st.code(gen_code, language="text", line_numbers=True)
            val = validate_robin(gen_code)
            if val["valid"]:
                st.success("✅ Clean & Paste-Validated for PAD 2.74 Designer!")
            else:
                st.warning(f"Validation diagnostics: {val.get('output', '')}")
            st.download_button(
                "⬇️ Download .robin File",
                data=gen_code,
                file_name=f"{recipe[0]}.robin",
                mime="text/plain"
            )

else:
    namelist = active_nupkg.namelist()
    infolist = active_nupkg.infolist()
    
    nuspec_names = [n for n in namelist if n.lower().endswith(".nuspec")]
    metadata = {}
    if nuspec_names:
        nuspec_content = active_nupkg.read(nuspec_names[0]).decode("utf-8", "ignore")
        metadata = parse_nuspec(nuspec_content)
    
    pkg_id = metadata.get("id", pkg_filename.replace(".nupkg", "").replace(".zip", ""))
    pkg_ver = metadata.get("version", "1.0.0")
    authors = metadata.get("authors", "Unknown")
    desc = metadata.get("description", "UiPath RPA Project")
    
    total_uncompressed = sum(info.file_size for info in infolist)
    
    # Header
    st.markdown(f'<div class="main-header">📦 {pkg_id} <span style="font-size: 1.1rem; color: #64748b;">v{pkg_ver}</span></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-header">{desc}</div>', unsafe_allow_html=True)
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Package ID", pkg_id)
    m2.metric("Version", pkg_ver)
    m3.metric("Files", f"{len(namelist)} items")
    m4.metric("Uncompressed Size", f"{total_uncompressed / 1024:.1f} KB")

    st.write("---")

    # Tabs
    tab_llm, tab_offline, tab_overview, tab_files, tab_viewer, tab_workflow, tab_project = st.tabs([
        "🧠 Pure LLM Converter (app_llm)",
        "🪄 Offline Converter & Recipes",
        "📋 Metadata & Dependencies",
        "🗂️ Package Files",
        "📄 File Viewer",
        "🤖 Workflows (XAML)",
        "⚙️ Project Configuration"
    ])

    # TAB 1: PURE LLM CONVERTER (PwC GenAI Gateway)
    with tab_llm:
        st.subheader("🏢 PwC GenAI Shared Service Converter (`app_llm.py` + `llm.py`)")
        st.markdown(
            "Configured exclusively for the **PwC GenAI APAC Gateway** (`https://genai-sharedservice-apac.pwcinternal.com/chat/completions`). "
            "Converts complete UiPath workflows into paste-ready Power Automate Desktop (Robin) scripts using your PwC API credentials."
        )

        st.info(f"🔒 **Target Gateway:** `{PWC_ENDPOINT}`")

        # Configuration row
        c_m, c_k = st.columns([1.5, 2])
        with c_m:
            chosen_model = st.selectbox(
                "PwC Gateway Model",
                PWC_MODELS,
                index=0,
                help="Pre-configured models available on the PwC GenAI Gateway."
            )
            if chosen_model == "Custom...":
                model_val = st.text_input("Enter Model Name", value="openai.global.gpt-4.1")
            else:
                model_val = chosen_model

        with c_k:
            api_key_val = st.text_input(
                "PwC Gateway API-Key",
                type="password",
                key="llm_api_key",
                placeholder="Paste your PwC API-Key...",
                help="Sent in the 'API-Key' header to the PwC GenAI gateway."
            )

        endpoint_val = PWC_ENDPOINT

        with st.expander("🔍 Gateway Model Helper (Verify Available Models for Your Key)"):
            st.caption("Test connectivity and list model entitlements configured for your PwC API Key.")
            if st.button("Check Available PwC Gateway Models"):
                if not api_key_val.strip():
                    st.warning("Please paste your PwC API Key above first.")
                else:
                    with st.spinner("Connecting to PwC GenAI Gateway..."):
                        avail = fetch_available_models(endpoint_val, api_key_val)
                    if avail:
                        st.success(f"Found {len(avail)} active models on your PwC Gateway entitlement:")
                        for m in avail:
                            st.write(f"- `{m}`")
                    else:
                        st.info("No models returned or endpoint requires direct payload selection. You can proceed with `openai.global.gpt-4.1`.")

        # File stats from extracted folder
        if extracted_folder_path:
            x_files = get_xaml_files(extracted_folder_path)
            d_files = get_dll_files(extracted_folder_path)
            k_files = get_important_files(extracted_folder_path)
            
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("XAML Workflows", len(x_files))
            sc2.metric("DLL Dependencies", len(d_files))
            sc3.metric("Key Config Files", len(k_files))

            # Trigger LLM button
            if st.button("🚀 Convert to PAD Robin with PwC GenAI", type="primary", use_container_width=True):
                if not api_key_val.strip():
                    st.error("🔑 Please enter your PwC Gateway API-Key to proceed.")
                    st.stop()

                with st.spinner("Extracting and optimizing XAML context for LLM..."):
                    raw_xml = build_xml_context(extracted_folder_path)
                    xml_context = compress_xaml_for_speed(raw_xml)
                    st.caption(f"Loaded {len(xml_context):,} characters of optimized workflow context.")

                with st.spinner(f"Calling LLM ({model_val}) via {endpoint_val}..."):
                    llm_result = llm_convert_to_robin(
                        api_key=api_key_val,
                        model=model_val,
                        xml_context=xml_context,
                        dlls=d_files,
                        endpoint=endpoint_val,
                    )

                if not llm_result.get("success"):
                    st.error(f"❌ **LLM Conversion Failed:**\n\n{llm_result.get('error')}")
                    if llm_result.get("raw_response"):
                        with st.expander("🔍 Raw Server Response"):
                            st.code(llm_result.get("raw_response"), language="text")
                else:
                    st.success(f"🤖 **Generated Exclusively by AI Model (`{llm_result.get('model_used')}`)**")
                    
                    if llm_result.get("summary"):
                        with st.expander("📋 Executive Business & Technical Summary", expanded=True):
                            st.write(llm_result.get("summary"))

                    robin_text = llm_result.get("robin_script", "")

                    # Copy instructions & plain text area
                    st.info(
                        "💡 **How to Paste into Power Automate Desktop:**\n"
                        "1. Click inside the **Plain Text Box** below and press **Ctrl + A → Ctrl + C**, or use the download button.\n"
                        "2. Open your desktop flow in Power Automate Desktop Designer.\n"
                        "3. Click on the flow canvas and press **Ctrl + V**."
                    )

                    st.text_area(
                        "Plain Text Robin Script (Copy-Safe: Ctrl+A → Ctrl+C)",
                        value=robin_text,
                        height=350,
                    )

                    # Validation
                    val_res = validate_robin(robin_text)
                    if val_res["valid"]:
                        st.success("✅ **PAD 2.74 Validated**: Clean paste syntax verified with 0 errors!")
                    else:
                        st.info("ℹ️ Script generated. Review actions above and paste into PAD.")

                    st.download_button(
                        label="📥 Download Robin Script (.txt)",
                        data=robin_text.encode("utf-8"),
                        file_name=f"{pkg_id}_robin_llm.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )

                    with st.expander("Formatted Code View"):
                        st.code(robin_text, language="text")

    # TAB 2: OFFLINE CONVERTER & RECIPES
    with tab_offline:
        st.subheader("⚡ Offline AST Converter & Recipes")
        xaml_files = [n for n in namelist if n.lower().endswith(".xaml")]
        if xaml_files:
            c_sel, c_btn = st.columns([3, 1])
            with c_sel:
                selected_xaml_to_convert = st.selectbox("Select Workflow (.xaml) to Convert:", xaml_files)
            with c_btn:
                st.write("")
                st.write("")
                convert_now = st.button("🚀 Fast Offline Convert", type="primary")

            if convert_now or "current_generated_robin" in st.session_state:
                if convert_now:
                    raw_xaml = active_nupkg.read(selected_xaml_to_convert).decode("utf-8", "ignore")
                    gen_robin = xaml_to_robin(raw_xaml)
                    st.session_state["current_generated_robin"] = gen_robin
                else:
                    gen_robin = st.session_state["current_generated_robin"]

                st.markdown("#### Generated Power Automate Desktop (Robin) Script:")
                st.code(gen_robin, language="text", line_numbers=True)

                col_v, col_d = st.columns([3, 1])
                with col_v:
                    val_res = validate_robin(gen_robin)
                    if val_res["valid"]:
                        st.success("✅ **Paste-Validated**: 0 syntax errors detected. Ready to paste directly into PAD Designer canvas!")
                    else:
                        st.info("ℹ️ Generated script ready. Review actions above and paste into PAD.")
                with col_d:
                    st.download_button(
                        "⬇️ Save as .robin File",
                        data=gen_robin,
                        file_name=f"{pkg_id}_flow.robin",
                        mime="text/plain"
                    )

        st.write("---")
        st.subheader("📚 Pre-built Automation Recipes")
        rec_col1, rec_col2 = st.columns([1, 2])
        with rec_col1:
            recipe_choice = st.selectbox(
                "Choose Automation Recipe:",
                [
                    ("folder_backup", "📁 Folder Backup (Downloads to Backup)"),
                    ("excel_report", "📊 Excel Invoice Data & Summary Report"),
                    ("outlook_attachments", "📧 Outlook Email & Attachment Extractor"),
                    ("input_and_decision", "❓ Interactive Input Dialog & Decision"),
                    ("sales_api_report", "🌐 REST API Request & Error Handling")
                ],
                format_func=lambda x: x[1]
            )
            if st.button("Generate Selected Recipe"):
                st.session_state["recipe_robin"] = generate_template_robin(recipe_choice[0])

        with rec_col2:
            if "recipe_robin" in st.session_state:
                rcode = st.session_state["recipe_robin"]
                st.code(rcode, language="text", line_numbers=True)
                st.download_button(
                    "⬇️ Download Recipe .robin",
                    data=rcode,
                    file_name=f"{recipe_choice[0]}.robin",
                    mime="text/plain"
                )

    # TAB 3: METADATA
    with tab_overview:
        st.subheader("Package Information")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Authors:** `{authors}`")
            st.markdown(f"**Tags:** `{metadata.get('tags', 'None')}`")
            st.markdown(f"**Require License Acceptance:** `{metadata.get('requireLicenseAcceptance', 'false')}`")
        with c2:
            st.markdown(f"**Package File:** `{pkg_filename}`")
            st.markdown(f"**Compressed Size:** `{len(pkg_bytes) / 1024:.1f} KB`")
            st.markdown(f"**Nuspec File:** `{nuspec_names[0] if nuspec_names else 'Not found'}`")

        st.markdown("### Dependencies")
        deps = metadata.get("dependencies", [])
        if deps:
            st.dataframe(deps, use_container_width=True)
        else:
            st.info("No external package dependencies declared in nuspec.")

    # TAB 4: FILES LIST
    with tab_files:
        st.subheader(f"Files in Package ({len(namelist)})")
        col_search, col_ext = st.columns([3, 1])
        with col_search:
            search_query = st.text_input("Filter files by name:", "")
        with col_ext:
            extensions = sorted(list(set(os.path.splitext(n)[1].lower() for n in namelist if "." in n)))
            selected_ext = st.selectbox("Filter by Extension:", ["All"] + extensions)

        file_rows = []
        for info in infolist:
            fname = info.filename
            ext = os.path.splitext(fname)[1].lower()
            if selected_ext != "All" and ext != selected_ext:
                continue
            if search_query and search_query.lower() not in fname.lower():
                continue
            file_rows.append({
                "Filename": fname,
                "Size (Bytes)": info.file_size,
                "Compressed (Bytes)": info.compress_size,
                "Type": ext or "folder/other"
            })

        st.dataframe(file_rows, use_container_width=True)

    # TAB 5: FILE VIEWER
    with tab_viewer:
        st.subheader("Inspect File Contents")
        text_friendly_exts = [".xaml", ".json", ".xml", ".nuspec", ".md", ".txt", ".cs", ".config", ".rels", ".psmdcp"]
        filtered_files = [n for n in namelist if any(n.lower().endswith(e) for e in text_friendly_exts)]
        all_choices = filtered_files if filtered_files else namelist

        selected_file_to_view = st.selectbox("Select file to preview:", all_choices)
        if selected_file_to_view:
            try:
                raw_data = active_nupkg.read(selected_file_to_view)
                ext = os.path.splitext(selected_file_to_view)[1].lower()
                lang_map = {
                    ".json": "json",
                    ".xaml": "xml",
                    ".xml": "xml",
                    ".nuspec": "xml",
                    ".rels": "xml",
                    ".md": "markdown",
                    ".cs": "csharp",
                    ".txt": "text"
                }
                lang = lang_map.get(ext, "text")
                text_content = raw_data.decode("utf-8", "ignore")

                st.download_button(
                    f"⬇️ Download {os.path.basename(selected_file_to_view)}",
                    data=raw_data,
                    file_name=os.path.basename(selected_file_to_view)
                )
                st.code(text_content, language=lang, line_numbers=True)
            except Exception as e:
                st.error(f"Could not preview this file: {e}")

    # TAB 6: WORKFLOWS (XAML)
    with tab_workflow:
        st.subheader("Workflow & Activity Analysis")
        xaml_files = [n for n in namelist if n.lower().endswith(".xaml")]
        if not xaml_files:
            st.info("No `.xaml` workflow files found in this package.")
        else:
            selected_xaml = st.selectbox("Select Workflow (.xaml):", xaml_files, key="analysis_xaml")
            if selected_xaml:
                xaml_data = active_nupkg.read(selected_xaml).decode("utf-8", "ignore")
                activities, variables, arguments = parse_xaml_activities(xaml_data)
                
                w1, w2, w3 = st.columns(3)
                w1.metric("Activities Detected", len(activities))
                w2.metric("Variables Defined", len(variables))
                w3.metric("Arguments Defined", len(arguments))

                if arguments:
                    st.markdown("#### Arguments")
                    st.dataframe(arguments, use_container_width=True)

                if variables:
                    st.markdown("#### Variables")
                    st.dataframe(variables, use_container_width=True)

                if activities:
                    st.markdown("#### Activities Used")
                    st.dataframe(activities, use_container_width=True)

    # TAB 7: PROJECT CONFIG
    with tab_project:
        st.subheader("Project Configuration")
        proj_json_files = [n for n in namelist if n.lower().endswith("project.json") or n.lower().endswith("package-descriptor.json")]
        if proj_json_files:
            for pjf in proj_json_files:
                st.markdown(f"#### 📄 `{pjf}`")
                try:
                    pdata = json.loads(active_nupkg.read(pjf).decode("utf-8", "ignore"))
                    st.json(pdata)
                except Exception as e:
                    st.error(f"Error parsing JSON: {e}")
        else:
            st.info("No `project.json` or `package-descriptor.json` found in package.")
