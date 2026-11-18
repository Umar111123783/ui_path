import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
import requests
from parser import (
    apply_robin_node_metadata,
    extract_robin_metadata_context,
    sanitize_robin_script,
)

REQUEST_TIMEOUT_SECONDS = 300
DEFAULT_MODEL_NAME = "openai.global.gpt-4.1"

SYSTEM_PROMPT = """You are an expert RPA migration engineer specialized in converting UiPath projects (XAML workflows, dependencies, selectors) into native Microsoft Power Automate Desktop (PAD) Robin language scripts.

You will receive the complete extracted context of a UiPath project, including project.json, all XAML workflows, and detected DLLs.

Your output MUST be a JSON object with two fields:
{
  "summary": "A concise executive business and technical summary of what this UiPath bot does, its inputs, outputs, activities mapped, and how it was translated to Power Automate Desktop.",
  "robin_script": "The complete, clean Power Automate Desktop (Robin) script ready to be pasted (Ctrl+V) directly into the Power Automate Desktop designer canvas."
}

CRITICAL RULES FOR POWER AUTOMATE DESKTOP (ROBIN) CANVAS PASTE SYNTAX:
1. CLEAN CANVAS PASTE FORMAT (NO HEADERS, DEBUG COMMENTS, OR FUNCTION MAIN):
   - For direct Ctrl+V pasting into the PAD designer canvas, do NOT wrap the main flow in 'FUNCTION Main ... END FUNCTION'. Output top-level bare action lines sequentially.
   - Subflows (if any other than Main exist) may be appended at the bottom using 'FUNCTION SubflowName ... END FUNCTION'.
   - Do NOT emit header banners ('# POWER AUTOMATE DESKTOP...', '# Project:...', '# Instructions:...'), '# node_id=...' metadata lines, '# Converted from...', or decorative '# ====' / '# ****' / '# ---' divider comments (such as '# --- Initialize Variables ---').
   - Only emit '# ...' lines for genuine Comment or Log activities from the source bot (every '#' line becomes a Comment action on the PAD canvas).
   - Do NOT output markdown fences or blank lines inside blocks.
   - Output PLAIN TEXT Robin syntax ONLY: NEVER HTML-encode characters (never output '&gt;', '&lt;', '&amp;', '&quot;', or '=&gt;'; use raw '>', '<', '&', '"', '=>'), and NEVER wrap URLs in HTML '<a href=...>...</a>' tags or Markdown '[url](url)' links.

2. EXACT NATIVE PAD ACTION IDENTIFIERS:
   - Web service: Web.InvokeWebService.InvokeWebService Url: $'''...''' Method: Web.Method.Get Accept: $'''application/json''' ContentType: $'''application/json''' ConnectionTimeout: 30 FollowRedirection: True ClearCookies: False FailOnErrorStatus: False EncodeRequestBody: True UserAgent: $'''Mozilla/5.0''' Encoding: Web.Encoding.AutoDetect AcceptUntrustedCertificates: False ResponseHeaders=> ResponseHeaders Response=> responseString StatusCode=> responseStatus
   - Messages: Display.ShowMessageDialog.ShowMessage Title: $'''...''' Message: $'''...''' Icon: Display.Icon.None Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False ButtonPressed=> ButtonPressed
   - Inputs: Display.InputDialog Title: $'''...''' Message: $'''...''' InputType: Display.InputType.SingleLine IsTopMost: False UserInput=> VarName ButtonPressed=> ButtonPressed
   - Convert text to number: Text.ToNumber Text: SourceTextVar Number=> TargetNumVar
   - Delays: Wait Delay: 2 (delay in seconds, never WAIT TODO_DURATION)
   - Stop execution on critical failure: EXIT Code: 0 (never FlowControl.StopFlow)
   - Subflows: CALL SubflowName (to run a local subflow)
   - Create DataTable: Variables.CreateNewDatatable InputTable: { ^['Col1', 'Col2'] } DataTable=> dtPosts
   - Insert DataRow: Variables.AddRowToDataTable.AppendRowToDataTable DataTable: dtPosts RowToAdd: [CurrentItem['col1'], CurrentItem['col2']]
   - Folder paths: Folder.GetSpecialFolder SpecialFolder: Folder.SpecialFolder.DesktopDirectory SpecialFolderPath=> SpecialFolderPath
   - Read Excel: Excel.ReadFromExcel.ReadAllCells Instance: ExcelInstance ReadAsText: False FirstLineIsHeader: True RangeValue=> dtData

3. SINGLE LINE PER ACTION & NEWLINES:
   - Every action statement MUST be strictly on a SINGLE CONTIGUOUS LINE.
   - Never insert a physical line break inside an action or inside a string parameter. For newlines in dialogs, use '\\r\\n' escape characters.

4. CONTROL FLOW, INDENTATION & CLEAN BLOCKS:
   - Every IF statement MUST have a matching END statement (IF ... THEN ... ELSE ... END).
   - Every LOOP statement MUST have a matching END statement.
   - Every SWITCH block uses: SWITCH varName ... CASE $'''val''' ... DEFAULT ... END (never END SWITCH or %varName%).
   - Use consistent 4-space indentation inside IF / ELSE IF / ELSE / END, LOOP / END, and SWITCH / END blocks, with no blank lines inside blocks.

5. VARIABLE SYNTAX & NUMERIC CONVERSION OF TEXT INPUTS:
   - Reference bare variable names in SET, SWITCH, IF/LOOP conditions, and action parameters (e.g. SET count TO jsonArray.Count, Json: responseString, RequestBody: requestBody, File: excelPath, Path: excelPath, DocumentPath: excelPath, Value: dtPosts, Text: userAgeText, IF count >= 10 THEN). Use %VarName% ONLY for string interpolation inside $'''...''' literals (NEVER bare %VarName% outside quotes, Automation Anywhere $Var$, or .NET constructors).
   - Initialize strings: SET VarName TO $''''''
   - Display.InputDialog always outputs a Text variable. Whenever an InputDialog or string variable is used in a numeric comparison (>=, >, <, <=) or numeric cast (CInt, Convert.ToInt32, CDbl), convert it first with Text.ToNumber and guard with ButtonPressed = $'''OK''':
     Display.InputDialog Title: $'''Age Checker''' Message: $'''Please enter your age''' InputType: Display.InputType.SingleLine IsTopMost: False UserInput=> userAgeText ButtonPressed=> ButtonPressed
     IF ButtonPressed = $'''OK''' THEN
         Text.ToNumber Text: userAgeText Number=> userAgeText_Num
         IF userAgeText_Num >= 18 THEN
             Display.ShowMessageDialog.ShowMessage Title: $'''Message''' Message: $'''You are an adult''' Icon: Display.Icon.None Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False ButtonPressed=> ButtonPressed
         ELSE
             Display.ShowMessageDialog.ShowMessage Title: $'''Message''' Message: $'''You are a Minor''' Icon: Display.Icon.None Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False ButtonPressed=> ButtonPressed
         END
     END
   - Initialize JSON objects: Variables.ConvertJsonToCustomObject Json: $'''{}''' CustomObject=> jsonObj
   - Initialize lists/arrays: Variables.CreateNewList List=> jsonArray

6. REST APIS & CRITICAL ERROR HANDLING:
   - Extract URLs from EndPoint or RequestUrl (e.g. Url: $'''https://jsonplaceholder.typicode.com/posts/%delPostId%''').
   - Method accuracy: When updating an existing post with a JSON request body, use Method: Web.Method.Put (never GET). For deleting, use Web.Method.Delete. For creating, use Web.Method.Post.
   - Response validation & Stop flow on critical errors:
     IF responseStatus < 200 OR responseStatus >= 300 THEN
         Display.ShowMessageDialog.ShowMessage Title: $'''API Error''' Message: $'''HTTP request failed with status: %responseStatus% %responseString%''' Icon: Display.Icon.None Buttons: Display.Buttons.OK DefaultButton: Display.DefaultButton.Button1 IsTopMost: False ButtonPressed=> ButtonPressed
         EXIT Code: 0
     END

7. EXCEL WORKBOOK & WORKSHEET SETUP:
   - Ensure the workbook file exists or create a blank one:
     IF (File.IfFile.Exists File: excelPath) THEN
         Excel.LaunchExcel.LaunchAndOpen Path: excelPath Visible: True ReadOnly: False LoadAddInsAndMacros: False Instance=> ExcelInstance
     ELSE
         Excel.LaunchExcel.Launch Visible: True LoadAddInsAndMacros: False Instance=> ExcelInstance
     END
   - Explicitly activate the worksheet: Excel.SetActiveWorksheet.ActivateWorksheetByName Instance: ExcelInstance Name: $'''Sheet1'''
   - Write headers and rows, then save and close:
     Excel.CloseExcel.CloseAndSaveAs Instance: ExcelInstance DocumentFormat: Excel.ExcelFormat.FromExtension DocumentPath: excelPath
"""

def _parse_llm_response(
    response_text: str,
    include_node_metadata: bool = False,
    workflow_name: str = "Workflow",
    var_types: Optional[Dict[str, str]] = None,
) -> Tuple[str, str]:
    """Extract (summary, sanitized_robin_script) from raw LLM text output."""
    if not response_text:
        return "", ""

    summary = ""
    robin_script: Any = ""

    clean_resp = response_text.strip()
    if "```json" in clean_resp:
        clean_resp = clean_resp.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in clean_resp:
        clean_resp = clean_resp.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        parsed = json.loads(clean_resp)
        if isinstance(parsed, dict):
            summary = str(parsed.get("summary", ""))
            robin_script = parsed.get("robin_script", "")
    except Exception:
        if "```" in response_text:
            blocks = re.findall(r'```(?:robin|text)?\s*(.*?)\s*```', response_text, re.DOTALL)
            if blocks:
                robin_script = blocks[0].strip()
                summary = re.sub(r'```(?:robin|text)?\s*.*?\s*```', '', response_text, flags=re.DOTALL).strip()
        if not robin_script and (
            "FUNCTION " in response_text
            or "SET " in response_text
            or "Display." in response_text
            or "IF " in response_text
        ):
            robin_script = response_text.strip()
            summary = "Robin script generated directly by LLM."

    if isinstance(robin_script, (list, dict)):
        robin_script = json.dumps(robin_script, indent=2, ensure_ascii=False)

    cleaned = sanitize_robin_script(
        str(robin_script or ""),
        keep_node_metadata=False,
        preserve_blank_lines=False,
    )
    if cleaned and include_node_metadata:
        cleaned = apply_robin_node_metadata(
            cleaned,
            workflow_name=workflow_name,
            var_types=var_types,
            reset_per_subflow=True,
        )
        cleaned = sanitize_robin_script(
            cleaned,
            keep_node_metadata=True,
            preserve_blank_lines=True,
        )
    return summary, cleaned


def is_local_endpoint(url: str) -> bool:
    """Return True if endpoint points to localhost / loopback."""
    host = (urlparse(url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _call_llm_api(
    api_key: str,
    model_name: str,
    system_message: str,
    user_message: str,
    endpoint: str,
) -> Tuple[str, Optional[str]]:
    """Execute chat completions request using API-Key header and model+messages payload."""
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
    }
    headers = {
        "accept": "application/json",
        "API-Key": api_key,
        "Authorization": f"Bearer {api_key}" if api_key else "",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return "", f"Could not connect to the LLM endpoint: {exc}"

    if not response.ok:
        detail = response.text.strip()[:1000]
        return "", f"LLM request failed with HTTP {response.status_code}. {detail}"

    try:
        response_data = response.json()
    except ValueError:
        return "", "The LLM endpoint returned a non-JSON response."

    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        return "", "The LLM response did not contain any choices."

    first_choice = choices[0]
    content = first_choice.get("message", {}).get("content")
    if isinstance(content, str) and content.strip():
        return content, None

    if isinstance(content, list):
        text_parts = [
            part["text"]
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        combined = "\n".join(text_parts).strip()
        if combined:
            return combined, None

    fallback = first_choice.get("text")
    if isinstance(fallback, str) and fallback.strip():
        return fallback, None

    return "", "The LLM response did not contain generated text."


def convert_to_robin(
    api_key: str,
    model: str,
    xml_context: str,
    dlls: List[str],
    temperature: float = 0.1,
    include_node_metadata: bool = False,
    endpoint: str = "",
) -> Dict[str, Any]:
    """
    Convert UiPath XML context and DLLs into a clean PAD Robin script and summary
    strictly using the configured chat completions LLM endpoint, with no local AST fallback.
    """
    del temperature  # Payload sends only model and messages to match the target API.
    clean_model = (model or "").strip()
    clean_endpoint = (endpoint or "").strip()
    clean_key = (api_key or "").strip()

    if not clean_endpoint:
        return {
            "success": False,
            "summary": "",
            "robin_script": "",
            "engine": "LLM",
            "error": "Endpoint URL is required for LLM conversion.",
            "raw_response": "",
            "model_used": clean_model,
            "endpoint_used": clean_endpoint,
        }

    parsed_ep = urlparse(clean_endpoint)
    if parsed_ep.scheme not in ("http", "https") or not parsed_ep.netloc:
        return {
            "success": False,
            "summary": "",
            "robin_script": "",
            "engine": "LLM",
            "error": "Endpoint must be a valid http:// or https:// URL.",
            "raw_response": "",
            "model_used": clean_model,
            "endpoint_used": clean_endpoint,
        }

    if not clean_model:
        return {
            "success": False,
            "summary": "",
            "robin_script": "",
            "engine": "LLM",
            "error": "Model name is required for LLM conversion.",
            "raw_response": "",
            "model_used": "",
            "endpoint_used": clean_endpoint,
        }

    if not clean_key and not is_local_endpoint(clean_endpoint):
        return {
            "success": False,
            "summary": "",
            "robin_script": "",
            "engine": "LLM",
            "error": "API Key is required for LLM conversion.",
            "raw_response": "",
            "model_used": clean_model,
            "endpoint_used": clean_endpoint,
        }

    prompt_content = (
        f"UiPath Project Extracted Context:\n{xml_context}\n\n"
        f"Detected DLL Dependencies:\n{', '.join(dlls) if dlls else 'None'}\n\n"
        "Convert this into clean, directly pasteable Power Automate Desktop (Robin) script and business summary in JSON format."
    )

    response_text, error_message = _call_llm_api(
        api_key=clean_key,
        model_name=clean_model,
        system_message=SYSTEM_PROMPT,
        user_message=prompt_content,
        endpoint=clean_endpoint,
    )

    Path("model_response.txt").write_text(
        response_text or error_message or "No model response generated.",
        encoding="utf-8",
    )

    if not response_text:
        return {
            "success": False,
            "summary": "",
            "robin_script": "",
            "engine": "LLM",
            "error": error_message or "No response received from the AI model.",
            "raw_response": error_message or "",
            "model_used": clean_model,
            "endpoint_used": clean_endpoint,
        }

    workflow_name, var_types = extract_robin_metadata_context(xml_context)
    summary, robin_script = _parse_llm_response(
        response_text,
        include_node_metadata=include_node_metadata,
        workflow_name=workflow_name,
        var_types=var_types,
    )
    if not robin_script:
        return {
            "success": False,
            "summary": summary,
            "robin_script": "",
            "engine": "LLM",
            "error": "The LLM responded, but did not return a valid Robin script.",
            "raw_response": response_text,
            "model_used": clean_model,
            "endpoint_used": clean_endpoint,
        }

    return {
        "success": True,
        "summary": summary,
        "robin_script": robin_script,
        "engine": "LLM",
        "error": None,
        "raw_response": response_text,
        "model_used": clean_model,
        "endpoint_used": clean_endpoint,
    }

