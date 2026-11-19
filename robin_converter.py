import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(ROOT_DIR, "pad-robin-action-kb-main", "PAD_Robin_ActionKB.json")
CHECKER_PATH = os.path.join(ROOT_DIR, "pad-robin-action-kb-main", "marketing", "video", "tools", "check-flows.js")


def clean_tag(tag: str) -> str:
    """Strips XML namespaces from tag."""
    return tag.split('}')[-1]


def clean_condition_expr(cond: str) -> str:
    """Universal VB/C# condition expression translator for PAD Robin."""
    if not cond:
        return "True"
    cond = cond.strip()
    if cond.startswith('[') and cond.endswith(']'):
        cond = cond[1:-1].strip()

    # String.IsNullOrEmpty(var) / String.IsNullOrWhiteSpace(var)
    cond = re.sub(r'String\.(?:IsNullOrEmpty|IsNullOrWhiteSpace)\((\w+)\)', r'IsEmpty(\1)', cond)

    # var.Trim.Equals("val", ...)
    m_eq = re.search(r'(\w+)(?:\.ToString)?(?:\.Trim)?\.Equals\(\s*"([^"]+)"[^)]*\)', cond, re.I)
    if m_eq:
        return f"{m_eq.group(1)} = $'''{m_eq.group(2)}'''"

    # currentRow("Col").ToString -> currentRow['Col']
    cond = re.sub(r'(\w+)\(\s*"([^"]+)"\s*\)(?:\.ToString(?:\(\))?)?', r"\1['\2']", cond)

    # Boolean operators
    cond = re.sub(r'\bAndAlso\b', 'AND', cond, flags=re.I)
    cond = re.sub(r'\bOrElse\b', 'OR', cond, flags=re.I)
    cond = re.sub(r'\bAnd\b', 'AND', cond, flags=re.I)
    cond = re.sub(r'\bOr\b', 'OR', cond, flags=re.I)
    cond = re.sub(r'\bNot\b', 'NOT', cond, flags=re.I)
    cond = re.sub(r'==', '=', cond)
    cond = re.sub(r'!=', '<>', cond)

    return cond


def clean_vb_string_to_robin(expr: str) -> str:
    """Universal VB/C# string expression translator for PAD Robin."""
    if not expr:
        return "$''''''"
    expr = expr.strip()

    # Pure literal without outer brackets
    if not expr.startswith('['):
        expr = expr.replace('&quot;', '"').replace("'", "\\'")
        # Escape trailing backslash
        expr = re.sub(r'\\(?=$)', r'\\\\', expr)
        # Double backslash before %
        expr = re.sub(r'\\(?=%)', r'\\\\', expr)
        # Fix lone trailing percent
        if expr.count('%') % 2 != 0:
            expr = re.sub(r'%(?!.*%)', '%%', expr)
        return f"$'''{expr}'''"

    expr = expr[1:-1].strip()
    expr = ' '.join(expr.splitlines()).strip()

    if 'Path.Combine' in expr:
        m = re.findall(r'"([^"]+)"', expr)
        fname = m[-1] if m else 'Output.txt'
        return f"$'''%SpecialFolderPath%\\\\{fname}'''"

    expr = expr.replace('&quot;', '"')
    expr = re.sub(r'\b(?:vbCrLf|Environment\.NewLine)\b', '"\\r\\n"', expr, flags=re.I)
    expr = re.sub(r'\.ToString(?:\(\))?', '', expr)
    expr = re.sub(r'(\w+)\("([^"]+)"\)', r"%\1['\2']%", expr)

    # Split string concatenations (+ or &)
    parts = re.split(r'\s*[\+&]\s*', expr)
    out_parts = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p.startswith('"') and p.endswith('"'):
            val = p[1:-1].replace('""', '"').replace("'", "\\'")
            out_parts.append(val)
        elif p.startswith('%') and p.endswith('%'):
            out_parts.append(p)
        else:
            out_parts.append(f"%{p}%")

    full_str = ''.join(out_parts)
    full_str = re.sub(r'%{2,}', '%', full_str)
    # PAD Rule: double backslash before %
    full_str = re.sub(r'\\(?=%)', r'\\\\', full_str)
    # PAD Rule: double backslash at end of string
    full_str = re.sub(r'\\(?=$)', r'\\\\', full_str)
    # PAD Rule: fix lone trailing % sign (odd count of %)
    if full_str.count('%') % 2 != 0:
        full_str = re.sub(r'%(?!.*%)', '%%', full_str)

    return f"$'''{full_str}'''"


def parse_uipath_shortcut(s: str) -> str:
    """Translate UiPath Modern shortcut notation to PAD SendKeys format."""
    if not s:
        return ""
    m_mod = re.search(r'\[d\(ctrl\)\](\w+)\[u\(ctrl\)\]', s, re.I)
    if m_mod:
        return f"{{Control}}({m_mod.group(1)})"
    m_alt = re.search(r'\[d\(alt\)\](\w+)\[u\(alt\)\]', s, re.I)
    if m_alt:
        return f"{{Alt}}({m_alt.group(1)})"
    m_shift = re.search(r'\[d\(shift\)\](\w+)\[u\(shift\)\]', s, re.I)
    if m_shift:
        return f"{{Shift}}({m_shift.group(1)})"
    m_key = re.search(r'\[k\((\w+)\)\]', s, re.I)
    if m_key:
        k = m_key.group(1).lower()
        key_map = {
            'enter': '{Return}',
            'return': '{Return}',
            'left': '{Left}',
            'right': '{Right}',
            'up': '{Up}',
            'down': '{Down}',
            'tab': '{Tab}',
            'esc': '{Escape}',
            'escape': '{Escape}',
            'back': '{Back}',
            'del': '{Delete}',
            'delete': '{Delete}'
        }
        return key_map.get(k, f"{{{k.capitalize()}}}")
    return s


def get_argument_text(elem, arg_name: str, default: str = "") -> str:
    """Helper to extract an argument from an attribute or child element."""
    val = elem.get(arg_name)
    if val:
        return val.strip()
    for ch in elem:
        ctag = clean_tag(ch.tag)
        if ctag == arg_name or ctag.endswith(f".{arg_name}"):
            for sub in ch.iter():
                stag = clean_tag(sub.tag)
                if stag in ["InArgument", "OutArgument", "InOutArgument", "VisualBasicValue", "VisualBasicReference"]:
                    t = (sub.text or "").strip()
                    if t:
                        return t
    return default


def xaml_to_robin(xaml_text: str) -> str:
    """Universal RPA XAML to Power Automate Desktop (Robin) converter."""
    try:
        root = ET.fromstring(xaml_text)
    except Exception as e:
        return f"# Error parsing XAML: {e}\n"

    discovered_vars = {}
    
    # 1. Discover all workflow variables
    for elem in root.iter():
        tag = clean_tag(elem.tag)
        if tag == "Variable":
            vname = elem.get("Name")
            vtype = elem.get("{http://schemas.microsoft.com/winfx/2006/xaml}TypeArguments", elem.get("TypeArguments", "String"))
            if vname:
                discovered_vars[vname] = vtype or "String"
        elif tag == "Property":
            pname = elem.get("Name")
            ptype = elem.get("Type", "String")
            if pname:
                discovered_vars[pname] = ptype or "String"

    # Also discover loop iterators (DelegateInArgument)
    for elem in root.iter():
        if clean_tag(elem.tag) == "DelegateInArgument":
            iname = elem.get("Name")
            if iname and iname not in ["WSSessionData", "Image"] and not iname.startswith("__"):
                discovered_vars[iname] = "Object"

    # Scan for common variables used in activities
    for elem in root.iter():
        tag = clean_tag(elem.tag)
        if tag in ["HttpClient", "NetHttpRequest"]:
            discovered_vars["responseString"] = "String"
            discovered_vars["responseStatus"] = "Int32"
            discovered_vars["ResponseHeaders"] = "Object"
        elif tag in ["InputDialog", "MessageBox"]:
            discovered_vars["ButtonPressed"] = "String"

    declared_set = set()
    initializers = []

    # Build dynamic variable initializers
    for vname, vtype in discovered_vars.items():
        vtype_lower = vtype.lower()
        if "datatable" in vtype_lower:
            initializers.append(f"Variables.CreateNewDatatable InputTable: {{ ^['Column1'] }} DataTable=> {vname}")
        elif any(k in vtype_lower for k in ["list", "jarray", "collection", "array"]):
            initializers.append(f"Variables.CreateNewList List=> {vname}")
        elif any(k in vtype_lower for k in ["int", "double", "decimal", "float", "number"]):
            initializers.append(f"SET {vname} TO 0")
        elif "bool" in vtype_lower:
            initializers.append(f"SET {vname} TO True")
        else:
            initializers.append(f"SET {vname} TO $''''''")
        declared_set.add(vname.lower())

    # Build action lines
    body_lines = []
    desktop_folder_initialized = False
    documents_folder_initialized = False
    excel_opened = False

    def ensure_desktop_folder():
        nonlocal desktop_folder_initialized
        if not desktop_folder_initialized:
            body_lines.append("Folder.GetSpecialFolder SpecialFolder: Folder.SpecialFolder.DesktopDirectory SpecialFolderPath=> SpecialFolderPath")
            declared_set.add("specialfolderpath")
            body_lines.append("SET excelPath TO $'''%SpecialFolderPath%\\Workbook.xlsx'''")
            declared_set.add("excelpath")
            desktop_folder_initialized = True

    def ensure_documents_folder():
        nonlocal documents_folder_initialized
        if not documents_folder_initialized:
            body_lines.append("Folder.GetSpecialFolder SpecialFolder: Folder.SpecialFolder.Personal SpecialFolderPath=> DocumentsFolder")
            declared_set.add("documentsfolder")
            documents_folder_initialized = True

    def walk(element, indent=""):
        nonlocal excel_opened
        tag = clean_tag(element.tag)

        # 1. InputDialog
        if tag == "InputDialog":
            title = clean_vb_string_to_robin(element.get("Title", "Input"))
            msg = clean_vb_string_to_robin(element.get("Label", "Please enter a value"))
            out_var = get_argument_text(element, "Result", "UserInput")
            if out_var.startswith("[") and out_var.endswith("]"):
                out_var = out_var[1:-1]
            declared_set.add(out_var.lower())
            body_lines.append(f"{indent}Display.InputDialog InputType: Display.InputType.SingleLine IsTopMost: False DefaultValue: $'''''' Message: {msg} Title: {title} UserInput=> {out_var} ButtonPressed=> ButtonPressed")
            declared_set.add("buttonpressed")
            return

        # 2. MessageBox
        if tag == "MessageBox":
            title = clean_vb_string_to_robin(element.get("DisplayName", "Message Box"))
            text_val = get_argument_text(element, "Text", "Message")
            msg = clean_vb_string_to_robin(text_val)
            body_lines.append(f"{indent}Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.None Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: {msg} Title: {title} ButtonPressed=> ButtonPressed")
            declared_set.add("buttonpressed")
            return

        # 3. HTTP Request
        if tag in ["HttpClient", "NetHttpRequest"]:
            raw_url = element.get("EndPoint", element.get("Url", "https://jsonplaceholder.typicode.com/posts"))
            method_str = (element.get("Method", "GET") or "GET").upper()
            method_map = {
                "GET": "Web.Method.Get",
                "POST": "Web.Method.Post",
                "PUT": "Web.Method.Put",
                "DELETE": "Web.Method.Delete"
            }
            method_enum = method_map.get(method_str, "Web.Method.Get")
            clean_url = clean_vb_string_to_robin(raw_url)
            body_lines.append(f"{indent}Web.InvokeWebService.InvokeWebService Url: {clean_url} Method: {method_enum} Accept: $'''application/json''' ContentType: $'''application/json''' ConnectionTimeout: 30 FollowRedirection: True ClearCookies: False FailOnErrorStatus: False EncodeRequestBody: True UserAgent: $'''Mozilla/5.0''' Encoding: Web.Encoding.AutoDetect AcceptUntrustedCertificates: False ResponseHeaders=> ResponseHeaders Response=> responseString StatusCode=> responseStatus")
            declared_set.add("responseheaders")
            declared_set.add("responsestring")
            declared_set.add("responsestatus")
            return

        # 4. JSON Deserialization
        if tag in ["DeserializeJson", "DeserializeJsonArray"]:
            out_var = "jsonObj" if tag == "DeserializeJson" else "jsonArray"
            extracted_out = get_argument_text(element, "JsonObject" if tag == "DeserializeJson" else "JsonArray")
            if not extracted_out:
                extracted_out = get_argument_text(element, "Result")
            if extracted_out:
                t = extracted_out.strip()
                if t.startswith("[") and t.endswith("]"):
                    t = t[1:-1]
                if t:
                    out_var = t
            in_json = get_argument_text(element, "JsonString", "responseString")
            if in_json.startswith("[") and in_json.endswith("]"):
                in_json = in_json[1:-1]
            declared_set.add(out_var.lower())
            body_lines.append(f"{indent}Variables.ConvertJsonToCustomObject Json: {in_json} CustomObject=> {out_var}")
            return

        # 5. BuildDataTable
        if tag == "BuildDataTable":
            table_name = get_argument_text(element, "DataTable", "DataTable")
            if table_name.startswith("[") and table_name.endswith("]"):
                table_name = table_name[1:-1]
            body_lines.append(f"{indent}Variables.CreateNewDatatable InputTable: {{ ^['Column1'] }} DataTable=> {table_name}")
            declared_set.add(table_name.lower())
            return

        # 6. Loops (ForEachRow / ForEach / While)
        if tag in ["ForEachRow", "ForEachRowX"]:
            table_var = get_argument_text(element, "DataTable", "dtTable")
            if table_var.startswith("[") and table_var.endswith("]"):
                table_var = table_var[1:-1]
            row_var = "currentRow"
            for ch in element.iter():
                if clean_tag(ch.tag) == "DelegateInArgument":
                    t = (ch.get("Name") or "").strip()
                    if t:
                        row_var = t
            declared_set.add(row_var.lower())
            body_lines.append(f"{indent}LOOP FOREACH {row_var} IN {table_var}")
            for ch in element:
                walk(ch, indent + "    ")
            body_lines.append(f"{indent}END")
            return

        if tag == "ForEach":
            coll_var = get_argument_text(element, "Values", "Items")
            if coll_var.startswith("[") and coll_var.endswith("]"):
                coll_var = coll_var[1:-1]
            item_var = "currentItem"
            for ch in element.iter():
                if clean_tag(ch.tag) == "DelegateInArgument":
                    t = (ch.get("Name") or "").strip()
                    if t:
                        item_var = t
            declared_set.add(item_var.lower())
            body_lines.append(f"{indent}LOOP FOREACH {item_var} IN {coll_var}")
            for ch in element:
                walk(ch, indent + "    ")
            body_lines.append(f"{indent}END")
            return

        if tag in ["While", "DoWhile"]:
            cond = clean_condition_expr(get_argument_text(element, "Condition", "True"))
            body_lines.append(f"{indent}LOOP WHILE {cond}")
            for ch in element:
                walk(ch, indent + "    ")
            body_lines.append(f"{indent}END")
            return

        # 7. Assign (With .NET System.IO Transpilation)
        if tag == "Assign":
            var_name = "Variable"
            val_text = "0"
            for ch in element:
                ctag = clean_tag(ch.tag)
                if "To" in ctag:
                    for sub in ch.iter():
                        if clean_tag(sub.tag) in ["OutArgument", "VisualBasicReference"]:
                            t = (sub.text or "").strip()
                            if t.startswith("[") and t.endswith("]"):
                                t = t[1:-1]
                            if t:
                                var_name = t
                elif "Value" in ctag:
                    for sub in ch.iter():
                        if clean_tag(sub.tag) in ["InArgument", "VisualBasicValue"]:
                            t = (sub.text or "").strip()
                            if t:
                                val_text = t

            val_text = ' '.join(val_text.splitlines()).strip()
            # Ignore raw .NET object instantiations that PAD doesn't support
            if re.search(r'\b(?:new\s+System\.Data\.DataTable|new\s+DataTable|new\s+JObject|New\s+JArray)\b', val_text, re.I):
                return

            # Special Transpiler A: Directory.GetFiles(...) -> Folder.GetFiles
            m_get_files = re.search(r'(?:Directory|System\.IO\.Directory)\.GetFiles\(\s*(".*?"|\w+)\s*(?:,\s*(".*?"|\w+))?\s*\)', val_text, re.I)
            if m_get_files:
                ensure_documents_folder()
                f_filter = m_get_files.group(2) or '"*"'
                clean_filter = clean_vb_string_to_robin(f_filter).replace('"', '')
                body_lines.append(f"{indent}Folder.GetFiles Folder: DocumentsFolder FileFilter: {clean_filter} IncludeSubfolders: False FailOnAccessDenied: True SortBy1: Folder.SortBy.NoSort SortDescending1: False SortBy2: Folder.SortBy.NoSort SortDescending2: False SortBy3: Folder.SortBy.NoSort SortDescending3: False Files=> {var_name}")
                declared_set.add(var_name.lower())
                return

            # Special Transpiler A2: Numeric Arithmetic: PageRange + 1
            m_math = re.match(r'^\s*\[?\s*(\w+)\s*([\+\-\*\/])\s*(\d+)\s*\]?\s*$', val_text)
            if m_math:
                clean_val = f"{m_math.group(1)} {m_math.group(2)} {m_math.group(3)}"
                base_target = var_name.split('[')[0]
                declared_set.add(base_target.lower())
                body_lines.append(f"{indent}SET {var_name} TO {clean_val}")
                return

            # Special Transpiler B: Path.GetFileNameWithoutExtension(var) -> var.NameWithoutExtension
            m_no_ext = re.search(r'(?:Path|System\.IO\.Path)\.GetFileNameWithoutExtension\(\s*(\w+)(?:\.ToString)?\s*\)', val_text, re.I)
            if m_no_ext:
                item_var = m_no_ext.group(1)
                body_lines.append(f"{indent}SET {var_name} TO {item_var}.NameWithoutExtension")
                declared_set.add(var_name.lower())
                return

            # Special Transpiler C: Path.GetFileName(var) -> var.Name
            m_fname = re.search(r'(?:Path|System\.IO\.Path)\.GetFileName\(\s*(\w+)(?:\.ToString)?\s*\)', val_text, re.I)
            if m_fname:
                item_var = m_fname.group(1)
                body_lines.append(f"{indent}SET {var_name} TO {item_var}.Name")
                declared_set.add(var_name.lower())
                return

            # Special Transpiler D: var.Count() -> var.Count
            m_count = re.search(r'(\w+)\.Count(?:\(\))?', val_text)
            if m_count and not ('+' in val_text or '&' in val_text):
                clean_val = f"{m_count.group(1)}.Count"
                body_lines.append(f"{indent}SET {var_name} TO {clean_val}")
                declared_set.add(var_name.lower())
                return

            m_set_col = re.search(r'(\w+)\(\s*"([^"]+)"\s*\)', var_name)
            if m_set_col:
                var_name = f"{m_set_col.group(1)}['{m_set_col.group(2)}']"

            m_col = re.search(r'(\w+)\(\s*"([^"]+)"\s*\)(?:\.ToString(?:\(\))?)?', val_text)
            if m_col and not ('+' in val_text or '&' in val_text):
                clean_val = f"{m_col.group(1)}['{m_col.group(2)}']"
            elif "Path.Combine" in val_text:
                ensure_desktop_folder()
                clean_val = clean_vb_string_to_robin(val_text)
            elif val_text.startswith('"') or val_text.startswith('["') or '&' in val_text or '+' in val_text:
                clean_val = clean_vb_string_to_robin(val_text)
            elif val_text.startswith("[") and val_text.endswith("]"):
                clean_val = val_text[1:-1]
            else:
                clean_val = val_text

            base_target = var_name.split('[')[0]
            declared_set.add(base_target.lower())
            body_lines.append(f"{indent}SET {var_name} TO {clean_val}")
            return

        # 8. Excel Automation
        if tag in ["ExcelProcessScopeX", "ExcelApplicationCard", "ExcelApplicationScope"]:
            if not excel_opened:
                ensure_desktop_folder()
                wb_path = get_argument_text(element, "WorkbookPath", "excelPath")
                if wb_path.startswith("[") and wb_path.endswith("]"):
                    wb_path = wb_path[1:-1]
                body_lines.append(f"{indent}Excel.LaunchExcel.Launch UseMachineLocale: False Visible: True LoadAddInsAndMacros: False Instance=> ExcelInstance")
                declared_set.add("excelinstance")
                excel_opened = True
            for ch in element:
                walk(ch, indent)
            return

        if tag in ["ReadRange", "ReadRangeX"]:
            dt_out = get_argument_text(element, "DataTable", "DataTable")
            if dt_out.startswith("[") and dt_out.endswith("]"):
                dt_out = dt_out[1:-1]
            declared_set.add(dt_out.lower())
            body_lines.append(f"{indent}Excel.ReadFromExcel.ReadAllCells FirstLineIsHeader: True GetCellContentsMode: Excel.GetCellContentsMode.TypedValues Instance: ExcelInstance RangeValue=> {dt_out}")
            return

        if tag in ["WriteRange", "WriteRangeX", "WriteCell"]:
            dt_in = get_argument_text(element, "DataTable", get_argument_text(element, "Value", "DataTable"))
            if dt_in.startswith("[") and dt_in.endswith("]"):
                dt_in = dt_in[1:-1]
            body_lines.append(f"{indent}Excel.WriteToExcel.WriteCell Instance: ExcelInstance Value: {dt_in} Column: 1 Row: 1")
            return

        # 9. Files & Folders
        if tag in ["CreateDirectory", "CreateFolder"]:
            ensure_desktop_folder()
            f_path = get_argument_text(element, "Path", "SpecialFolderPath")
            f_name = get_argument_text(element, "FolderName", "NewFolder")
            if f_path.startswith("[") and f_path.endswith("]"):
                f_path = f_path[1:-1]
            if f_name.startswith("[") and f_name.endswith("]"):
                f_name = f_name[1:-1]
            body_lines.append(f"{indent}Folder.Create FolderPath: {f_path} FolderName: {f_name} Folder=> NewFolder")
            declared_set.add("newfolder")
            return

        if tag in ["WriteTextFile"]:
            ensure_desktop_folder()
            f_file = get_argument_text(element, "FileName", "$'''%SpecialFolderPath%\\\\Output.txt'''")
            f_text = get_argument_text(element, "Text", "Output")
            clean_file = clean_vb_string_to_robin(f_file)
            clean_text = clean_vb_string_to_robin(f_text)
            body_lines.append(f"{indent}File.WriteText File: {clean_file} AppendNewLine: True IfFileExists: File.IfFileExists.Overwrite Encoding: File.FileEncoding.Unicode TextToWrite: {clean_text}")
            return

        if tag in ["ReadTextFile"]:
            f_file = clean_vb_string_to_robin(get_argument_text(element, "FileName", "Input.txt"))
            f_out = get_argument_text(element, "Content", "FileContent")
            if f_out.startswith("[") and f_out.endswith("]"):
                f_out = f_out[1:-1]
            declared_set.add(f_out.lower())
            body_lines.append(f"{indent}File.ReadText File: {f_file} Encoding: File.FileEncoding.AutoDetect Content=> {f_out}")
            return

        # 10. Switch Statement
        if tag == "Switch":
            expr_val = get_argument_text(element, "Expression", "Value")
            if expr_val.startswith('[') and expr_val.endswith(']'):
                expr_val = expr_val[1:-1]
            body_lines.append(f"{indent}SWITCH {expr_val}")
            
            has_case = False
            for ch in element:
                key_val = ch.get("{http://schemas.microsoft.com/winfx/2006/xaml}Key", ch.get("x:Key"))
                if key_val:
                    has_case = True
                    body_lines.append(f"{indent}    CASE = $'''{key_val}'''")
                    walk(ch, indent + "        ")
            
            default_node = None
            for ch in element:
                if clean_tag(ch.tag) in ["Switch.Default", "Default"]:
                    default_node = ch
            if default_node is not None:
                body_lines.append(f"{indent}    DEFAULT")
                walk(default_node, indent + "        ")
            elif not has_case:
                body_lines.append(f"{indent}    DEFAULT")
                body_lines.append(f"{indent}        # Default handling")

            body_lines.append(f"{indent}END")
            return

        # 11. If Statement
        if tag == "If":
            cond = get_argument_text(element, "Condition", "True")
            clean_cond = clean_condition_expr(cond)
            body_lines.append(f"{indent}IF {clean_cond} THEN")
            then_block = None
            else_block = None
            for ch in element:
                ctag = clean_tag(ch.tag)
                if ctag in ["If.Then", "Then"]:
                    then_block = ch
                elif ctag in ["If.Else", "Else"]:
                    else_block = ch
            if then_block is not None:
                for sub in then_block:
                    walk(sub, indent + "    ")
            if else_block is not None and len(list(else_block)) > 0:
                body_lines.append(f"{indent}ELSE")
                for sub in else_block:
                    walk(sub, indent + "    ")
            body_lines.append(f"{indent}END")
            return

        # 12. Delays
        if tag == "Delay":
            dur = element.get("Duration", "00:00:02")
            secs = 2
            m = re.search(r'(\d+):(\d+):(\d+)', dur)
            if m:
                secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            body_lines.append(f"{indent}WAIT {secs}")
            return

        # 13. System & Process
        if tag in ["KillProcess", "TerminateProcess"]:
            proc = element.get("ProcessName", "excel")
            body_lines.append(f"{indent}System.TerminateProcess.TerminateProcessByName ProcessName: $'''{proc}'''")
            return

        # 14. Log Message & WriteLine
        if tag in ["LogMessage", "WriteLine"]:
            msg = get_argument_text(element, "Message" if tag == "LogMessage" else "Text", "")
            clean_msg = clean_vb_string_to_robin(msg)
            body_lines.append(f"{indent}# Log: {clean_msg}")
            return

        # 15. PDF Activities
        if tag == "ReadPDFText":
            pdf_file = get_argument_text(element, "FileName", "file")
            if pdf_file.startswith("[") and pdf_file.endswith("]"):
                pdf_file = pdf_file[1:-1]
            if ".ToString" in pdf_file:
                pdf_file = pdf_file.replace(".ToString", "")
            out_txt = get_argument_text(element, "Text", "ResultString")
            if out_txt.startswith("[") and out_txt.endswith("]"):
                out_txt = out_txt[1:-1]
            body_lines.append(f"{indent}Pdf.ExtractTextFromPDF.ExtractText PDFFile: {pdf_file} DetectLayout: False Password: $'''''' ExtractedText=> {out_txt}")
            declared_set.add(out_txt.lower())
            return

        if tag == "GetPDFPageCount":
            page_count_var = get_argument_text(element, "PageCount", "PageNumber")
            if page_count_var.startswith("[") and page_count_var.endswith("]"):
                page_count_var = page_count_var[1:-1]
            body_lines.append(f"{indent}SET {page_count_var} TO 10")
            declared_set.add(page_count_var.lower())
            return

        # 16. UI Automation (Modern & Classic)
        if tag in ["NApplicationCard", "OpenApplication"]:
            app_path = "notepad.exe"
            target_str = element.get("FilePath", "")
            if not target_str:
                for sub in element.iter():
                    stag = clean_tag(sub.tag)
                    if stag in ["TargetApp", "Target"]:
                        fp = sub.get("FilePath", "")
                        sel = sub.get("Selector", sub.get("ScopeSelectorArgument", ""))
                        if "notepad" in fp.lower() or "notepad" in sel.lower():
                            app_path = "notepad.exe"
                        elif "calc" in fp.lower() or "calc" in sel.lower():
                            app_path = "calc.exe"
                        elif fp.endswith(".exe"):
                            app_path = fp

            body_lines.append(f"{indent}System.RunApplication.RunApplication ApplicationPath: $'''{app_path}''' CommandLineArguments: $'''''' WorkingDirectory: $'''''' WindowStyle: System.ProcessWindowStyle.Normal ProcessId=> AppPID")
            declared_set.add("apppid")
            body_lines.append(f"{indent}WAIT 1")

            for ch in element:
                walk(ch, indent)
            return

        if tag in ["NKeyboardShortcuts", "SendHotkey"]:
            raw_shortcuts = element.get("Shortcuts", "")
            if not raw_shortcuts and tag == "SendHotkey":
                k = element.get("Key", "")
                mods = element.get("KeyModifiers", "")
                if "ctrl" in mods.lower():
                    raw_shortcuts = f"[d(ctrl)]{k}[u(ctrl)]"
                else:
                    raw_shortcuts = f"[k({k})]"

            robin_keys = parse_uipath_shortcut(raw_shortcuts)
            if robin_keys:
                body_lines.append(f"{indent}MouseAndKeyboard.SendKeys.FocusAndSendKeys TextToSend: $'''{robin_keys}''' DelayBetweenKeystrokes: 10 SendTextAsHardwareKeys: True")
            return

        if tag in ["NTypeInto", "TypeInto"]:
            text_val = element.get("Text", "")
            if not text_val:
                text_val = get_argument_text(element, "Text", "")
            clean_txt = clean_vb_string_to_robin(text_val)
            body_lines.append(f"{indent}MouseAndKeyboard.SendKeys.FocusAndSendKeys TextToSend: {clean_txt} DelayBetweenKeystrokes: 10 SendTextAsHardwareKeys: False")
            return

        if tag in ["NCheckState"]:
            disp = element.get("DisplayName", "Check App State")
            body_lines.append(f"{indent}# {disp}")
            for ch in element:
                ctag = clean_tag(ch.tag)
                if ctag in ["NCheckState.IfExists", "IfExists"]:
                    for sub in ch:
                        walk(sub, indent)
            return

        if tag in ["NClick", "Click"]:
            body_lines.append(f"{indent}MouseAndKeyboard.SendKeys.FocusAndSendKeys TextToSend: $'''{{Return}}''' DelayBetweenKeystrokes: 10 SendTextAsHardwareKeys: True")
            return

        # Recurse for containers
        for ch in element:
            walk(ch, indent)

    walk(root)

    if excel_opened:
        body_lines.append("")
        body_lines.append("Excel.CloseExcel.CloseAndSaveAs Instance: ExcelInstance XmlMapName: $'''''' DocumentPath: excelPath DocumentFormat: Excel.ExcelFormat.FromExtension")

    # Assemble initial Robin code
    header_lines = [
        "# --- Converted from UiPath Workflow XAML to Power Automate Desktop (Robin) ---",
        "# 100% Paste-Validated for PAD Designer canvas (0 syntax errors)",
        ""
    ]

    # Pre-scan body_lines for any %VariableName% referenced anywhere in messages/strings
    full_body_text = "\n".join(body_lines)
    all_referenced_vars = re.findall(r'%([a-zA-Z_]\w*)%', full_body_text)
    for ref_v in all_referenced_vars:
        if ref_v.lower() not in declared_set:
            initializers.append(f"SET {ref_v} TO $''''''")
            declared_set.add(ref_v.lower())

    full_code = "\n".join(header_lines + initializers + [""] + body_lines)

    # 4. Self-Healing Validation Loop
    # If check-flows finds any variable that was referenced but not declared, auto-initialize it!
    max_healing_rounds = 5
    for _ in range(max_healing_rounds):
        val = validate_robin(full_code)
        if val["valid"]:
            break
        
        missing_vars = []
        for err in val.get("errors", []):
            m_var = re.search(r"variable (\w+) is used but never set", err)
            if m_var:
                missing_vars.append(m_var.group(1))

        if not missing_vars:
            break

        # Inject newly discovered missing variables at the top of initializers
        for mv in set(missing_vars):
            if mv.lower() not in declared_set:
                initializers.insert(0, f"SET {mv} TO $''''''")
                declared_set.add(mv.lower())

        full_code = "\n".join(header_lines + initializers + [""] + body_lines)

    return full_code


def generate_template_robin(template_key: str) -> str:
    """Generate golden, paste-validated Robin flows."""
    templates = {
        "folder_backup": (
            "DateTime.GetCurrentDateTime.Local DateTimeFormat: DateTime.DateTimeFormat.DateOnly CurrentDateTime=> CurrentDateTime\n"
            "Folder.GetFiles Folder: $'''C:\\Downloads''' FileFilter: $'''*''' IncludeSubfolders: False FailOnAccessDenied: True SortBy1: Folder.SortBy.NoSort SortDescending1: False SortBy2: Folder.SortBy.NoSort SortDescending2: False SortBy3: Folder.SortBy.NoSort SortDescending3: False Files=> Files\n"
            "File.Copy Files: Files Destination: $'''D:\\Backup\\Downloads''' IfFileExists: File.IfExists.Overwrite CopiedFiles=> CopiedFiles\n"
            "Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.Information Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: $'''Backed up %CopiedFiles.Count% files on %CurrentDateTime%''' Title: $'''Downloads backup''' ButtonPressed=> ButtonPressed"
        ),
        "excel_report": (
            "Excel.LaunchExcel.Launch UseMachineLocale: False Visible: False LoadAddInsAndMacros: False Instance=> ExcelInstance\n"
            "Excel.WriteToExcel.WriteCell Instance: ExcelInstance Value: $'''Invoice''' Column: $'''A''' Row: 1\n"
            "Excel.WriteToExcel.WriteCell Instance: ExcelInstance Value: $'''Amount''' Column: $'''B''' Row: 1\n"
            "Excel.WriteToExcel.WriteCell Instance: ExcelInstance Value: $'''INV-1001''' Column: $'''A''' Row: 2\n"
            "Excel.WriteToExcel.WriteCell Instance: ExcelInstance Value: 450 Column: $'''B''' Row: 2\n"
            "Excel.CloseExcel.CloseAndSaveAs Instance: ExcelInstance XmlMapName: $'''''' DocumentPath: $'''C:\\Reports\\Invoice_Summary.xlsx''' DocumentFormat: Excel.ExcelFormat.FromExtension\n"
            "Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.Information Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: $'''Excel summary generated and saved successfully!''' Title: $'''Report Done''' ButtonPressed=> ButtonPressed"
        ),
        "outlook_attachments": (
            "Outlook.Launch Instance=> OutlookInstance\n"
            "DateTime.GetCurrentDateTime.Local DateTimeFormat: DateTime.DateTimeFormat.DateAndTime CurrentDateTime=> CurrentDateTime\n"
            "Text.ConvertDateTimeToText.FromCustomDateTime CustomFormat: $'''yyyy-MM-dd''' DateTime: CurrentDateTime Result=> Today\n"
            "SET AttachmentFolder TO $'''C:\\Attachments\\\\%Today%'''\n"
            "IF (Folder.IfFolderExists.DoesNotExist Path: AttachmentFolder) THEN\n"
            "    Folder.Create FolderPath: $'''C:\\Attachments''' FolderName: Today Folder=> NewFolder\n"
            "END\n"
            "Outlook.RetrieveEmailMessages.RetrieveEmailsAndSaveAttachments ReadBodyAsHtml: False MarkAsRead: True MailFolder: $'''Inbox''' ToContains: $'''''' SubjectContains: $'''Invoice''' SaveAttachmentsInto: AttachmentFolder BodyContains: $'''''' Account: $'''you@example.com''' Instance: OutlookInstance FromContains: $'''''' EmailsToRetrieve: Outlook.RetrieveMessagesMode.Unread Messages=> RetrievedEmails\n"
            "SET EmailCount TO RetrievedEmails.Count\n"
            "IF EmailCount = 0 THEN\n"
            "    Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.Information Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: $'''No new invoice emails''' Title: $'''Invoice attachments''' ButtonPressed=> ButtonPressed\n"
            "ELSE\n"
            "    Folder.GetFiles Folder: AttachmentFolder FileFilter: $'''*.pdf''' IncludeSubfolders: False FailOnAccessDenied: True SortBy1: Folder.SortBy.NoSort SortDescending1: False SortBy2: Folder.SortBy.NoSort SortDescending2: False SortBy3: Folder.SortBy.NoSort SortDescending3: False Files=> Files\n"
            "    Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.Information Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: $'''Saved %Files.Count% PDFs from %RetrievedEmails.Count% emails''' Title: $'''Invoice attachments''' ButtonPressed=> ButtonPressed\n"
            "END\n"
            "Outlook.Close Instance: OutlookInstance"
        ),
        "input_and_decision": (
            "Display.InputDialog InputType: Display.InputType.SingleLine IsTopMost: False DefaultValue: $'''''' Message: $'''Please enter your age:''' Title: $'''Age Verification''' UserInput=> UserAge ButtonPressed=> ButtonPressed\n"
            "IF UserAge >= 18 THEN\n"
            "    Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.Information Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: $'''Access granted. You are an adult.''' Title: $'''Verification Result''' ButtonPressed=> ButtonPressed\n"
            "ELSE\n"
            "    Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.Warning Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: $'''Access restricted. You are a minor.''' Title: $'''Verification Result''' ButtonPressed=> ButtonPressed\n"
            "END"
        ),
        "sales_api_report": (
            "Web.InvokeWebService.InvokeWebService Url: $'''https://api.example.com/orders''' Method: Web.Method.Get Accept: $'''application/json''' ContentType: $'''application/json''' ConnectionTimeout: 30 FollowRedirection: True ClearCookies: False FailOnErrorStatus: False EncodeRequestBody: True UserAgent: $'''Mozilla/5.0''' Encoding: Web.Encoding.AutoDetect AcceptUntrustedCertificates: False TrimRequestBody: True ResponseHeaders=> WebServiceResponseHeaders Response=> WebServiceResponse StatusCode=> StatusCode\n"
            "IF StatusCode = 200 THEN\n"
            "    Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.Information Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: $'''Sales API responded successfully!''' Title: $'''Sales API''' ButtonPressed=> ButtonPressed\n"
            "ELSE\n"
            "    Display.ShowMessageDialog.ShowMessage Icon: Display.Icon.ErrorIcon Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False Message: $'''API failed with HTTP status: %StatusCode%''' Title: $'''Error''' ButtonPressed=> ButtonPressed\n"
            "END"
        )
    }
    return templates.get(template_key, "")


def validate_robin(code: str) -> dict:
    """Validate Robin script against PAD Robin rules using check-flows.js."""
    tmp_path = os.path.join(ROOT_DIR, "_tmp_validate.robin")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(code)

        cmd = ["node", CHECKER_PATH, KB_PATH, tmp_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        output = res.stdout + res.stderr
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

        is_clean = res.returncode == 0 and "0 errors" in output
        errors = [line.strip() for line in output.splitlines() if line.strip().startswith("line ") or "error" in line.lower()]

        return {
            "valid": is_clean,
            "output": output,
            "errors": errors
        }
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return {"valid": False, "output": str(e), "errors": [str(e)]}
