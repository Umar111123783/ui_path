"""
Universal Expression Parser and Transpiler for VB.NET / C# to PAD Robin expressions.
"""
import re

def clean_tag(tag: str) -> str:
    """Strips XML namespaces from tag."""
    if not tag:
        return ""
    return tag.split('}')[-1]

def clean_indexer(s: str) -> str:
    """Converts VB .Item(...) indexers and dictionary calls to Robin brackets."""
    if not s:
        return ""
    # .Item("key") -> ['key']
    s = re.sub(r'\.Item\(\s*"([^"]+)"\s*\)', r"['\1']", s)
    # .Item(idx) -> [idx]
    s = re.sub(r'\.Item\(\s*([^)]+)\s*\)', r'[\1]', s)
    # var("col") -> var['col']
    s = re.sub(r'(\w+)\(\s*"([^"]+)"\s*\)', r"\1['\2']", s)
    return s

def clean_condition_expr(cond: str) -> str:
    """Universal VB/C# condition expression translator for PAD Robin."""
    if not cond:
        return "True"
    cond = cond.strip()
    if cond.startswith('[') and cond.endswith(']'):
        cond = cond[1:-1].strip()

    # String.IsNullOrEmpty(var) / String.IsNullOrWhiteSpace(var) -> IsEmpty(var)
    cond = re.sub(r'String\.(?:IsNullOrEmpty|IsNullOrWhiteSpace)\((\w+)\)', r'IsEmpty(\1)', cond)

    # Special .Split condition: NOT var.Split(":"C)(0)...Equals("VAL")
    m_not_split_eq = re.search(r'\bNOT\s+(\w+)\.Split\(\s*"([^"]+)"C?\)\s*\((\d+)\)(?:\.ToString)?(?:\.ToUpper)?(?:\.Trim)?\.Equals\(\s*"([^"]+)"[^)]*\)', cond, re.I)
    if m_not_split_eq:
        src = m_not_split_eq.group(1)
        idx = m_not_split_eq.group(3)
        val = m_not_split_eq.group(4)
        return f"{src}_Split[{idx}] <> $'''{val}'''"

    m_split_eq = re.search(r'(\w+)\.Split\(\s*"([^"]+)"C?\)\s*\((\d+)\)(?:\.ToString)?(?:\.ToUpper)?(?:\.Trim)?\.Equals\(\s*"([^"]+)"[^)]*\)', cond, re.I)
    if m_split_eq:
        src = m_split_eq.group(1)
        idx = m_split_eq.group(3)
        val = m_split_eq.group(4)
        return f"{src}_Split[{idx}] = $'''{val}'''"

    def clean_operand(op: str) -> str:
        op = clean_indexer(op.strip())
        op = re.sub(r'\.ToString(?:\(\))?', '', op, flags=re.I)
        op = re.sub(r'\.ToUpper(?:\(\))?', '', op, flags=re.I)
        op = re.sub(r'\.ToLower(?:\(\))?', '', op, flags=re.I)
        op = re.sub(r'\.Trim(?:\(\))?', '', op, flags=re.I)
        op = re.sub(r'\.Replace\(\s*"[^"]*"\s*,\s*"[^"]*"\s*\)', '', op, flags=re.I)
        if (op.startswith('"') and op.endswith('"')) or (op.startswith("'") and op.endswith("'")):
            lit = op[1:-1].replace("'", "\\'")
            op = f"$'''{lit}'''"
        return op.strip()

    # General .Equals(...) translation: (NOT )? expr1.Equals(expr2)
    m_gen_eq = re.search(r'^(?:(NOT)\s+)?(.+?)\.Equals\((.+)\)$', cond, re.I)
    if m_gen_eq:
        is_not = bool(m_gen_eq.group(1))
        left = clean_operand(m_gen_eq.group(2))
        right = clean_operand(m_gen_eq.group(3))
        op = "<>" if is_not else "="
        return f"{left} {op} {right}"

    cond = clean_indexer(cond)
    cond = re.sub(r'\.ToString(?:\(\))?', '', cond, flags=re.I)
    cond = re.sub(r'\.ToUpper(?:\(\))?', '', cond, flags=re.I)
    cond = re.sub(r'\.Trim(?:\(\))?', '', cond, flags=re.I)

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
        expr = re.sub(r'\\(?=$)', r'\\\\', expr)
        expr = re.sub(r'\\(?=%)', r'\\\\', expr)
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
            var_clean = re.sub(r'\.(?:ToString|Replace|Trim|ToUpper|ToLower)(?:\([^)]*\))?', '', p, flags=re.I).strip()
            out_parts.append(f"%{var_clean}%")

    full_str = ''.join(out_parts)
    full_str = re.sub(r'%{2,}', '%', full_str)
    full_str = re.sub(r'\\(?=%)', r'\\\\', full_str)
    full_str = re.sub(r'\\(?=$)', r'\\\\', full_str)
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
