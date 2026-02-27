from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import os
import sys
from io import StringIO
import traceback
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI()

# ✅ Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Request Model
# ---------------------------

class CodeRequest(BaseModel):
    code: str

class ErrorAnalysis(BaseModel):
    error_lines: List[int]

# ---------------------------
# Tool Function
# ---------------------------

def execute_python_code(code: str) -> dict:
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    try:
        exec(code)
        output = sys.stdout.getvalue()
        return {"success": True, "output": output}

    except Exception:
        output = traceback.format_exc()
        return {"success": False, "output": output}

    finally:
        sys.stdout = old_stdout

# ---------------------------
# AI Error Analysis
# ---------------------------

def analyze_error_with_ai(code: str, tb: str) -> List[int]:
    prompt = f"""
Analyze this Python code and its traceback.
Return ONLY the line numbers where the error occurred.

CODE:
{code}

TRACEBACK:
{tb}
"""

    model = genai.GenerativeModel("gemini-2.0-flash")

    response = model.generate_content(
        prompt,
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": {
                "type": "object",
                "properties": {
                    "error_lines": {
                        "type": "array",
                        "items": {"type": "integer"}
                    }
                },
                "required": ["error_lines"]
            }
        }
    )

    result = ErrorAnalysis.model_validate_json(response.text)
    return result.error_lines

# ---------------------------
# Endpoint
# ---------------------------

@app.post("/code-interpreter")
async def run_code(request: CodeRequest):

    execution = execute_python_code(request.code)

    if execution["success"]:
        return {
            "error": [],
            "result": execution["output"]
        }

    # Only call AI if error occurred
    error_lines = analyze_error_with_ai(
        request.code,
        execution["output"]
    )

    return {
        "error": error_lines,
        "result": execution["output"]
    }