

from app.utils.database import save_feedback_db   # 🔥 ADD THIS
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FEEDBACK_FILE = BASE_DIR / "feedback_log.json"


def save_feedback(feedback):

    entry = {
        "code": feedback.code,
        "rating": feedback.rating,
        "comment": feedback.comment,
        "timestamp": datetime.utcnow().isoformat()
    }

    # 🔥 STEP 1: SAVE TO DB
    save_feedback_db(
        feedback.code,
        feedback.rating,
        feedback.comment
    )

    print("✅ Feedback saved to PostgreSQL")

    # 🔥 STEP 2: SAVE TO JSON (as proper JSON array)
    try:
        # Read existing feedback data
        if FEEDBACK_FILE.exists():
            with open(FEEDBACK_FILE, "r") as f:
                feedback_data = json.load(f)
        else:
            feedback_data = []

        # Append new entry
        feedback_data.append(entry)

        # Write back as proper JSON array
        with open(FEEDBACK_FILE, "w") as f:
            json.dump(feedback_data, f, indent=2)

        print("✅ Feedback saved to JSON file")

    except Exception as e:
        print(f"❌ Error saving to JSON file: {e}")
        # Continue anyway since DB save succeeded

    return {"message": "Feedback saved successfully"}