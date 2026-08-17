def detect_language(code: str) -> str:

    code = code.lower()

    if "def " in code or "import " in code:
        return "python"

    if "public static void main" in code:
        return "java"

    if "console.log" in code or "function(" in code:
        return "javascript"

    if "#include" in code:
        return "c/c++"

    return "unknown"