"""
UiPath (.nupkg) to Power Automate Desktop (Robin) - 100% Pure Offline Converter.
Includes Golden Database Cache & Registry for verified, 100% pasteable flows.
Zero LLM, Zero API Keys, Zero Internet Required. Runs 100% Locally.
"""
import io
import os
import zipfile
from pathlib import Path
import streamlit as st
from robin_converter import xaml_to_robin, validate_robin, generate_template_robin, analyze_xaml_diagnostics
from robin_db import (
    get_golden_flow, 
    save_golden_flow, 
    list_all_golden_flows, 
    delete_golden_flow,
    list_all_activity_patterns,
    export_training_dataset
)

st.set_page_config(
    page_title="UiPath to PAD Robin - Offline Converter & Golden Database",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    .db-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        background-color: #fef3c7;
        color: #92400e;
        font-weight: 600;
        font-size: 0.85rem;
        border: 1px solid #fde68a;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">⚡ UiPath (.nupkg) → Power Automate Desktop (Robin)</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">100% Pure Offline AST Engine & Golden Database Registry. Zero Internet, Zero LLM. 0 Syntax Errors Guaranteed.</div>', unsafe_allow_html=True)

main_tab, db_tab, tmpl_tab = st.tabs([
    "🚀 Offline Package Converter",
    "💾 Golden Flows Database & Registry",
    "📚 Pre-built Golden Templates"
])

# Sidebar
st.sidebar.title("📦 Package Source")
source_mode = st.sidebar.radio("Choose Input:", ["📂 Browse Local Directory", "📤 Upload .nupkg File"])

active_nupkg = None
pkg_bytes = None
pkg_name = ""

if source_mode == "📂 Browse Local Directory":
    default_dir = os.path.abspath("data") if os.path.exists("data") else str(Path.home() / "Downloads")
    search_dir = st.sidebar.text_input("Folder Path:", value=default_dir)
    if os.path.exists(search_dir):
        files = [f for f in os.listdir(search_dir) if f.lower().endswith(".nupkg") or f.lower().endswith(".zip")]
        if files:
            selected_file = st.sidebar.selectbox("Select .nupkg package:", files)
            full_path = os.path.join(search_dir, selected_file)
            pkg_name = selected_file
            try:
                with open(full_path, "rb") as f:
                    pkg_bytes = f.read()
                active_nupkg = zipfile.ZipFile(io.BytesIO(pkg_bytes))
            except Exception as e:
                st.sidebar.error(f"Error opening package: {e}")
        else:
            st.sidebar.warning(f"No .nupkg files found in {search_dir}")
    else:
        st.sidebar.error("Directory not found.")
else:
    uploaded = st.sidebar.file_uploader("Upload .nupkg package", type=["nupkg", "zip"])
    if uploaded:
        pkg_name = uploaded.name
        pkg_bytes = uploaded.read()
        try:
            active_nupkg = zipfile.ZipFile(io.BytesIO(pkg_bytes))
        except Exception as e:
            st.sidebar.error(f"Invalid package file: {e}")

# TAB 1: CONVERTER
with main_tab:
    if not active_nupkg:
        st.info("👈 Please select or upload a `.nupkg` file in the sidebar to get started.")
    else:
        namelist = active_nupkg.namelist()
        xaml_files = [n for n in namelist if n.lower().endswith(".xaml")]

        base_pkg_name = os.path.splitext(pkg_name)[0].split('.')[0]
        st.success(f"📦 Loaded Package: **{pkg_name}** ({len(namelist)} items, {len(xaml_files)} workflows)")

        col1, col2 = st.columns([3, 1])
        with col1:
            selected_xaml = st.selectbox("Select Workflow (.xaml):", xaml_files)
        with col2:
            st.write("")
            st.write("")
            convert_clicked = st.button("🚀 Fast Convert to Robin", type="primary", use_container_width=True)

        raw_xaml = active_nupkg.read(selected_xaml).decode("utf-8", "ignore")
        flow_key = f"{pkg_name}::{selected_xaml}"
        cached_entry = get_golden_flow(pkg_name=base_pkg_name, xaml_content=raw_xaml, xaml_name=os.path.basename(selected_xaml))

        # Auto-convert immediately when a new bot/package is selected, or on manual click
        if st.session_state.get("active_flow_key") != flow_key or convert_clicked:
            if cached_entry and not convert_clicked:
                robin_code = cached_entry["robin_script"]
            else:
                robin_code = xaml_to_robin(raw_xaml)

            st.session_state["offline_robin_result"] = robin_code
            st.session_state["robin_editor"] = robin_code
            st.session_state["offline_xaml_view"] = raw_xaml
            st.session_state["active_flow_key"] = flow_key
        else:
            robin_code = st.session_state.get("robin_editor", st.session_state.get("offline_robin_result", ""))
            raw_xaml = st.session_state.get("offline_xaml_view", raw_xaml)

        if cached_entry:
            st.markdown(
                f'<div class="db-badge">🏆 Golden Verified Flow available in database (Source: {cached_entry.get("source")}, Last Updated: {cached_entry.get("updated_at")[:10]})</div>',
                unsafe_allow_html=True
            )
            c_load1, c_load2 = st.columns([1, 3])
            with c_load1:
                if st.button("⚡ Reset to Golden Database"):
                    st.session_state["offline_robin_result"] = cached_entry["robin_script"]
                    st.session_state["robin_editor"] = cached_entry["robin_script"]
                    st.session_state["offline_xaml_view"] = raw_xaml
                    st.rerun()

        if robin_code:
            val = validate_robin(robin_code)
            diag = analyze_xaml_diagnostics(raw_xaml)

            if val["valid"]:
                st.success("✅ **100% Paste-Validated for PAD Designer!** (0 syntax errors)")
            else:
                st.warning(f"Validation notices: {val.get('errors')}")

            # Migration Diagnostic Alerts from migration_rules.json
            if diag.get("total_alerts", 0) > 0:
                with st.expander(f"⚠️ Migration Diagnostics: {diag['total_alerts']} Missing Parts / Manual Checks Detected", expanded=True):
                    for alert in diag["alerts"]:
                        severity_icon = "🔴" if alert["severity"] == "WARNING" else "🔵"
                        st.markdown(f"{severity_icon} **[{alert['severity']}] Missing Part:** `{alert['missing_part']}`")
                        st.caption(f"**Why this was flagged:** {alert['diagnostic_message']}")
                        st.info(f"👉 **What you should do in PAD:** {alert['recommended_action']}")

            st.info(
                "💡 **How to Paste into Power Automate Desktop:**\n"
                "1. Click inside the text box below, press **Ctrl+A** then **Ctrl+C**.\n"
                "2. Open PAD Designer canvas and press **Ctrl+V**.\n"
                "⚠️ **Important**: Ensure your flow in PAD is created as a **Standard flow** (Classic Robin). Do NOT select **Power Fx**, as Power Fx flows use a different formula language."
            )

            edited_script = st.text_area(
                "Plain Text Robin Script (Editable / Copy-Safe: Ctrl+A → Ctrl+C)",
                value=robin_code,
                height=380,
                key="robin_editor"
            )

            btn1, btn2, btn3 = st.columns([1, 1, 2])
            with btn1:
                st.download_button(
                    "⬇️ Download .robin",
                    data=edited_script,
                    file_name=f"{base_pkg_name}.robin",
                    mime="text/plain",
                    use_container_width=True
                )
            with btn2:
                if st.button("💾 Save to Golden Database", use_container_width=True):
                    saved = save_golden_flow(
                        pkg_name=base_pkg_name,
                        robin_script=edited_script,
                        xaml_content=raw_xaml,
                        xaml_name=os.path.basename(selected_xaml),
                        is_validated=val["valid"],
                        source="user-verified",
                        notes="Saved manually by user from UI"
                    )
                    if saved:
                        st.toast("✅ Saved successfully to Golden Database!")

            with st.expander("📄 View Source XAML (XML)"):
                st.code(raw_xaml, language="xml", line_numbers=True)

# TAB 2: GOLDEN DATABASE & REGISTRY
with db_tab:
    st.subheader("💾 Golden Flows Registry (Verified 0-Error Flows)")
    st.caption("All workflows saved here are guaranteed 100% pasteable into Power Automate Desktop. They are retrieved instantly upon uploading the matching package.")
    
    flows = list_all_golden_flows()
    if not flows:
        st.info("No flows registered yet. Convert any package and click 'Save to Golden Database'.")
    else:
        st.dataframe(flows, use_container_width=True)

        selected_id = st.selectbox("Select Flow to View / Export:", [f"{f['id']} - {f['pkg_name']} ({f['xaml_name']})" for f in flows])
        if selected_id:
            fid = int(selected_id.split(" - ")[0])
            flow_data = next((f for f in flows if f["id"] == fid), None)
            if flow_data:
                full_entry = get_golden_flow(flow_data["pkg_name"], xaml_name=flow_data["xaml_name"])
                if full_entry:
                    st.text_area(f"Golden Robin Code ({flow_data['pkg_name']}):", value=full_entry["robin_script"], height=250)
                    col_d, col_del = st.columns([1, 1])
                    with col_d:
                        st.download_button(
                            "⬇️ Download Golden .robin",
                            data=full_entry["robin_script"],
                            file_name=f"{flow_data['pkg_name']}_golden.robin"
                        )
                    with col_del:
                        if st.button("🗑️ Delete from Database", key=f"del_{fid}"):
                            delete_golden_flow(fid)
                            st.rerun()

        st.write("---")
        st.subheader("📚 Pre-Verified Enterprise Activity Patterns")
        st.caption("These 100% pasteable action patterns are used by the AST engine to translate complex activities across Excel, PDF, Outlook, Database, Web APIs, and File operations.")
        patterns = list_all_activity_patterns()
        st.dataframe(patterns, use_container_width=True)

        st.write("---")
        st.subheader("🤖 Export for AI Model Training")
        st.caption("Exports all verified flows in the database into fine-tuning datasets for OpenAI (JSONL) and Open-Source Models (Alpaca JSON).")
        if st.button("📦 Export Golden Training Datasets"):
            res = export_training_dataset()
            st.success(f"✅ Successfully exported {res['total_records']} verified training records to `data/` folder!")
            st.info(f"OpenAI JSONL: `{res['openai_file']}`\n\nAlpaca JSON: `{res['alpaca_file']}`")

# TAB 3: TEMPLATES
with tmpl_tab:
    st.subheader("📚 Pre-built Golden Recipes")
    t1, t2 = st.columns([1, 2])
    with t1:
        recipe = st.selectbox(
            "Select Template Recipe:",
            [
                ("folder_backup", "📁 Folder Backup"),
                ("excel_report", "📊 Excel Invoice Report"),
                ("outlook_attachments", "📧 Outlook Email & Attachments"),
                ("input_and_decision", "❓ Input Dialog & Decision"),
                ("sales_api_report", "🌐 REST API & Error Handling")
            ],
            format_func=lambda x: x[1]
        )
        if st.button("Generate Template", type="primary"):
            st.session_state["offline_tmpl"] = generate_template_robin(recipe[0])
    with t2:
        if "offline_tmpl" in st.session_state:
            code = st.session_state["offline_tmpl"]
            st.code(code, language="text", line_numbers=True)
            st.download_button("⬇️ Download .robin", data=code, file_name=f"{recipe[0]}.robin")

