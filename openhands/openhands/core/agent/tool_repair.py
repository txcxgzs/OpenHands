"""
工具调用修复和JSON修复工具

Hermes风格的工具调用参数自动修复：
- 修复截断的JSON
- 处理尾随逗号
- 修复Python None等
"""

import json
import re
import logging

logger = logging.getLogger(__name__)


def escape_invalid_chars_in_json_strings(raw: str) -> str:
    """Escape unescaped control chars inside JSON string values."""
    out = []
    in_string = False
    i = 0
    n = len(raw)
    
    while i < n:
        ch = raw[i]
        if in_string:
            if ch == '\\' and i + 1 < n:
                out.append(ch)
                out.append(raw[i + 1])
                i += 2
                continue
            elif ch == '"':
                in_string = False
            elif ord(ch) < 32 and ch not in '\\nrt':
                out.append(f'\\u{ord(ch):04x}')
                i += 1
                continue
            out.append(ch)
        else:
            if ch == '"':
                in_string = True
            out.append(ch)
        i += 1
    
    return ''.join(out)


def repair_tool_call_arguments(raw_args: str, tool_name: str = "?") -> str:
    """Attempt to repair malformed tool_call argument JSON.
    
    Models can produce truncated JSON, trailing commas, Python None, etc.
    This function applies common repairs; if all fail it returns "{}".
    """
    raw_stripped = raw_args.strip() if isinstance(raw_args, str) else ""
    
    # Fast-path: empty / whitespace-only -> empty object
    if not raw_stripped:
        logger.warning("Sanitized empty tool_call arguments for %s", tool_name)
        return "{}"
    
    # Python-literal None -> normalise to {}
    if raw_stripped == "None":
        logger.warning("Sanitized Python-None tool_call arguments for %s", tool_name)
        return "{}"
    
    # Repair pass 0: Try json.loads with strict=False
    try:
        parsed = json.loads(raw_stripped, strict=False)
        reserialised = json.dumps(parsed, separators=(",", ":"))
        if reserialised != raw_stripped:
            logger.warning("Repaired unescaped control chars in tool_call arguments for %s", tool_name)
        return reserialised
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    
    # Attempt common JSON repairs
    fixed = raw_stripped
    
    # 1. Strip trailing commas before } or ]
    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
    
    # 2. Close unclosed structures
    open_curly = fixed.count('{') - fixed.count('}')
    open_bracket = fixed.count('[') - fixed.count(']')
    if open_curly > 0:
        fixed += '}' * open_curly
    if open_bracket > 0:
        fixed += ']' * open_bracket
    
    # 3. Remove excess closing braces/brackets
    for _ in range(50):
        try:
            json.loads(fixed)
            break
        except json.JSONDecodeError:
            if fixed.endswith('}') and fixed.count('}') > fixed.count('{'):
                fixed = fixed[:-1]
            elif fixed.endswith(']') and fixed.count(']') > fixed.count('['):
                fixed = fixed[:-1]
            else:
                break
    
    try:
        json.loads(fixed)
        logger.warning(
            "Repaired malformed tool_call arguments for %s: %s → %s",
            tool_name, raw_stripped[:80], fixed[:80],
        )
        return fixed
    except json.JSONDecodeError:
        pass
    
    # Repair pass 4: escape unescaped control chars
    try:
        escaped = escape_invalid_chars_in_json_strings(fixed)
        if escaped != fixed:
            json.loads(escaped)
            logger.warning(
                "Repaired control-char tool_call arguments for %s: %s → %s",
                tool_name, raw_stripped[:80], escaped[:80],
            )
            return escaped
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    
    # Last resort: replace with empty object
    logger.warning(
        "Unrepairable tool_call arguments for %s — replaced with empty object",
        tool_name,
    )
    return "{}"


def validate_tool_arguments(tool_name: str, arguments: dict, schema: dict) -> tuple[bool, str]:
    """Validate tool arguments against schema.
    
    Returns (is_valid, error_message)
    """
    if not schema or 'parameters' not in schema:
        return True, ""
    
    properties = schema.get('parameters', {}).get('properties', {})
    required = schema.get('parameters', {}).get('required', [])
    
    # Check required parameters
    for req in required:
        if req not in arguments:
            return False, f"Missing required parameter: {req}"
    
    # Type validation
    for param_name, param_value in arguments.items():
        if param_name not in properties:
            continue
        
        expected_type = properties[param_name].get('type')
        
        if expected_type == 'string' and not isinstance(param_value, str):
            return False, f"Parameter {param_name} must be string, got {type(param_value).__name__}"
        elif expected_type == 'number' and not isinstance(param_value, (int, float)):
            return False, f"Parameter {param_name} must be number"
        elif expected_type == 'boolean' and not isinstance(param_value, bool):
            return False, f"Parameter {param_name} must be boolean"
        elif expected_type == 'array' and not isinstance(param_value, list):
            return False, f"Parameter {param_name} must be array"
        elif expected_type == 'object' and not isinstance(param_value, dict):
            return False, f"Parameter {param_name} must be object"
    
    return True, ""


def coerce_tool_arguments(arguments: dict, schema: dict) -> dict:
    """Coerce argument types to match schema.
    
    Converts string numbers to int/float, string booleans, etc.
    """
    if not schema or 'parameters' not in schema:
        return arguments
    
    properties = schema.get('parameters', {}).get('properties', {})
    coerced = {}
    
    for param_name, param_value in arguments.items():
        if param_name not in properties:
            coerced[param_name] = param_value
            continue
        
        expected_type = properties[param_name].get('type')
        
        # String to number
        if expected_type == 'number' and isinstance(param_value, str):
            try:
                if '.' in param_value:
                    coerced[param_name] = float(param_value)
                else:
                    coerced[param_name] = int(param_value)
            except ValueError:
                coerced[param_name] = param_value
        # String to boolean
        elif expected_type == 'boolean':
            if isinstance(param_value, str):
                coerced[param_name] = param_value.lower() in ('true', '1', 'yes', 'on')
            else:
                coerced[param_name] = bool(param_value)
        # Ensure number is int when schema says integer
        elif expected_type == 'integer' and isinstance(param_value, float):
            if param_value.is_integer():
                coerced[param_name] = int(param_value)
            else:
                coerced[param_name] = param_value
        else:
            coerced[param_name] = param_value
    
    return coerced
