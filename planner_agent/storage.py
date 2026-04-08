import json 
from pathlib import Path
from schemas import UserBookRequest , BookPlan

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

def save_book_plan(plan: BookPlan , filename: str = "book_plan.json") -> Path:
    output_path = OUTPUT_DIR / filename
    output_path.write_text(
        json.dumps(
            plan.model_dump(),
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    return output_path
