import json
import re



def strip_code_fences(text: str) -> str:
    """
    Removes ```json ... ``` or ``` ... ``` wrappers.
    """
    text = text.strip()

    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()

    return text

def extract_json_block(text: str) -> str:
    """
    Extracts JSON object from text if extra content is present.
    """

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON object found in the text.")
    
    return text[start:end+1]


def load_json_safe(text: str):
    """
    Full pipeline:
    1. remove fences
    2. extract JSON
    3. prase
    """

    cleaned = strip_code_fences(text)
    json_block = extract_json_block(cleaned)

    try:
        return json.loads(json_block)
    except json.JSONDecodeError as e:
        context_radius = 80
        start = max(0, e.pos - context_radius)
        end = min(len(json_block), e.pos + context_radius)
        context = json_block[start:end].replace("\n", "\\n")
        raise ValueError(
            "Failed to parse JSON: "
            f"{e.msg} at line {e.lineno}, column {e.colno}. "
            f"Context: {context}"
        ) from e
    

