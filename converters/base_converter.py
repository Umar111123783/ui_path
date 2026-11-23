"""
Base Activity Converter and translation router.
"""
import re
from typing import List
from core.project_model import ActivityNode
from core.conversion_context import ConversionContext
from parsers.expression_parser import (
    clean_tag, clean_condition_expr, clean_vb_string_to_robin, parse_uipath_shortcut
)

STRUCTURAL_TAGS = {
    "Activity", "Sequence", "Flowchart", "FlowStep", "FlowDecision", "FlowSwitch",
    "Collection", "AssemblyReference", "String", "Dictionary", "Boolean", "Int32",
    "ViewStateData", "IdRef", "VisualBasicValue", "VisualBasicReference",
    "InArgument", "OutArgument", "InOutArgument", "TargetAnchorable", "TargetApp",
    "Target", "VerifyOptions", "Variable", "Variables", "Sequence.Variables", "List",
    "Property", "DelegateInArgument", "Catch", "Catches", "TryCatch.Catches",
    "TryCatch.Finally", "TryCatch.Try", "Members", "Null", "Literal"
}

class BaseConverter:
    def __init__(self, context: ConversionContext):
        self.ctx = context

    def convert_node(self, node: ActivityNode, indent: str = "") -> List[str]:
        lines = []
        tag = node.type_name
        props = node.properties
        disp = node.display_name or tag

        # 1. Assign
        if tag in ["Assign", "MultipleAssign"]:
            var_name = props.get("To", "Variable")
            val_text = props.get("Value", "0")
            for sub in node.children:
                if "To" in sub.type_name:
                    var_name = sub.properties.get("Value", sub.display_name)
                elif "Value" in sub.type_name:
                    val_text = sub.properties.get("Value", sub.display_name)
            
            if var_name.startswith("[") and var_name.endswith("]"):
                var_name = var_name[1:-1]
            if val_text.startswith("[") and val_text.endswith("]"):
                val_text = val_text[1:-1]

            m_split = re.search(r'(\w+)\.Split\(\s*"([^"]+)"C?\)\s*\((\d+)\)', val_text, re.I)
            if m_split:
                src_var = m_split.group(1)
                delim = m_split.group(2)
                idx = m_split.group(3)
                split_var = f"{src_var}_Split"
                if not self.ctx.is_variable_declared(split_var):
                    lines.append(f"{indent}Text.SplitText.SplitWithDelimiter Text: {src_var} IsRegEx: False CustomDelimiter: $'''{delim}''' Result=> {split_var}")
                    self.ctx.register_variable(split_var)
                lines.append(f"{indent}SET {var_name} TO {split_var}[{idx}]")
                self.ctx.register_variable(var_name.split('[')[0])
                return lines

            clean_val = clean_vb_string_to_robin(f"[{val_text}]") if ('+' in val_text or '"' in val_text) else val_text
            lines.append(f"{indent}SET {var_name} TO {clean_val}")
            self.ctx.register_variable(var_name.split('[')[0])
            return lines

        # 2. Control Flow: If
        if tag == "If":
            cond = props.get("Condition", "True")
            clean_cond = clean_condition_expr(cond)
            lines.append(f"{indent}IF {clean_cond} THEN")
            for child in node.children:
                if "Then" in child.type_name:
                    for sub in child.children:
                        lines.extend(self.convert_node(sub, indent + "    "))
                elif "Else" in child.type_name and child.children:
                    lines.append(f"{indent}ELSE")
                    for sub in child.children:
                        lines.extend(self.convert_node(sub, indent + "    "))
            lines.append(f"{indent}END")
            return lines

        # 3. Loops: While / ForEach / ForEachRow
        if tag in ["While", "DoWhile"]:
            cond = clean_condition_expr(props.get("Condition", "True"))
            lines.append(f"{indent}LOOP WHILE {cond}")
            for child in node.children:
                lines.extend(self.convert_node(child, indent + "    "))
            lines.append(f"{indent}END")
            return lines

        if tag in ["ForEachRow", "ForEachRowX", "ForEach"]:
            item_var = props.get("CurrentRow", props.get("item", "CurrentItem"))
            collection = props.get("DataTable", props.get("Values", "Items"))
            lines.append(f"{indent}LOOP FOREACH {item_var} IN {collection}")
            self.ctx.register_variable(item_var)
            for child in node.children:
                lines.extend(self.convert_node(child, indent + "    "))
            lines.append(f"{indent}END")
            return lines

        # 4. Logging
        if tag in ["LogMessage", "WriteLine"]:
            msg = props.get("Message", props.get("Text", ""))
            clean_msg = clean_vb_string_to_robin(msg)
            lvl = props.get("Level", "Info").lower()
            lvl_map = {"warn": "WarningLevel", "warning": "WarningLevel", "error": "ErrorLevel", "fatal": "ErrorLevel"}
            lvl_enum = f"Logging.LogLevel.{lvl_map.get(lvl, 'InfoLevel')}"
            lines.append(f"{indent}Logging.LogMessage Message: {clean_msg} LogLevel: {lvl_enum}")
            return lines

        # 5. File Operations
        if tag == "ReadTextFile":
            f_file = clean_vb_string_to_robin(props.get("FileName", "Input.txt"))
            f_out = props.get("Content", "FileContent")
            lines.append(f"{indent}File.ReadTextFromFile.ReadText File: {f_file} Encoding: File.TextFileEncoding.UTF8 Content=> {f_out}")
            self.ctx.register_variable(f_out)
            return lines

        if tag == "WriteTextFile":
            f_file = clean_vb_string_to_robin(props.get("FileName", "Output.txt"))
            f_text = clean_vb_string_to_robin(props.get("Text", "Output"))
            lines.append(f"{indent}File.WriteText File: {f_file} AppendNewLine: True IfFileExists: File.IfFileExists.Overwrite Encoding: File.FileEncoding.UTF8 TextToWrite: {f_text}")
            return lines

        # 6. Exceptions
        if tag in ["Throw", "Rethrow"]:
            lines.append(f"{indent}FlowControl.ThrowCustomError CustomErrorCode: $'''BusinessRuleException''' CustomErrorMessage: $'''Exception thrown in workflow'''")
            return lines

        # 7. UI / Dialog
        if tag == "CustomInput" or tag == "InputDialog":
            out_res = props.get("Result", "UserInput")
            if out_res.startswith("[") and out_res.endswith("]"):
                out_res = out_res[1:-1]
            lines.append(f"{indent}Display.InputDialog InputType: Display.InputType.SingleLine IsTopMost: False DefaultValue: $'''''' Message: $'''Enter input:''' Title: $'''User Input''' UserInput=> {out_res} ButtonPressed=> ButtonPressed")
            self.ctx.register_variable(out_res)
            self.ctx.register_variable("ButtonPressed")
            return lines

        if tag in ["NTypeInto", "TypeInto"]:
            text_val = props.get("Text", "")
            text_val = re.sub(r'\[k\((?:enter|return)\)\]', '{Return}', text_val, flags=re.I)
            clean_txt = clean_vb_string_to_robin(text_val)
            lines.append(f"{indent}MouseAndKeyboard.SendKeys.FocusAndSendKeys TextToSend: {clean_txt} DelayBetweenKeystrokes: 10 SendTextAsHardwareKeys: False")
            return lines

        if tag in ["NClick", "Click"]:
            lines.append(f"{indent}MouseAndKeyboard.SendKeys.FocusAndSendKeys TextToSend: $'''{{Return}}''' DelayBetweenKeystrokes: 10 SendTextAsHardwareKeys: True")
            return lines

        if tag == "NKeyboardShortcuts":
            raw_s = props.get("Shortcuts", "")
            keys = parse_uipath_shortcut(raw_s)
            if keys:
                lines.append(f"{indent}MouseAndKeyboard.SendKeys.FocusAndSendKeys TextToSend: $'''{keys}''' DelayBetweenKeystrokes: 10 SendTextAsHardwareKeys: True")
            return lines

        # Recurse for containers
        before = len(lines)
        for child in node.children:
            lines.extend(self.convert_node(child, indent))
        after = len(lines)

        # Fallback activity capture
        if before == after and tag not in STRUCTURAL_TAGS and "." not in tag:
            lines.append(f"{indent}# Activity: {disp} [{tag}]")

        return lines
