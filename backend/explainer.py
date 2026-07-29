# backend/explainer.py
import json
# pyrefly: ignore [missing-import]
from groq import Groq
from config import get_api_key

class ExplainerService:
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.model = model

    def analyze(self, anomaly_line: int, context_str: str, mode: str = "general", matched_code: str = "") -> str:
        api_key = get_api_key()
        if not api_key:
            raise ValueError("Groq API Key is not configured. Please supply a key.")
            
        client = Groq(api_key=api_key)
        
        code_context = f"\n\n[MATCHED WORKSPACE SOURCE FILE]\n{matched_code}\n[/MATCHED WORKSPACE SOURCE FILE]" if matched_code else ""

        if mode == "general":
            prompt = f"""
Analyze this log segment. The main issue is at line {anomaly_line} (marked '-->').
{code_context}

[LOG SEGMENT]
{context_str}
[/LOG SEGMENT]

Generate a simplified, non-technical explanation for people who do not have a background in coding.
Strictly structure your response using these headers:

### 1. Where the Error Is
Explain clearly which system component (database, files, internet connection, etc.) ran into an issue.

### 2. What the Error Is
Describe what went wrong in plain, conversational English. Use everyday analogies (e.g., explaining a deadlock like cars blocking an intersection).

### 3. How to Fix It
Provide simple, non-technical step-by-step instructions. Do not supply complex code edits. Focus on simple actions like resetting servers, freeing disk space, or checking credentials.
"""
        else: # Technical SRE / Dev Mode
            prompt = f"""
Perform a deep SRE root cause analysis of this log segment. The issue anchor line is {anomaly_line} (marked '-->').
{code_context}

[LOG SEGMENT]
{context_str}
[/LOG SEGMENT]

Generate a highly detailed, technical report for developers and systems engineers. 
Strictly structure your response using these headers:

### 1. Where the Error Is
Identify the line number, stack frame trace, and exact classes/methods involved.

### 2. What the Error Is
Discuss the underlying technical mechanisms (e.g., deadlock, thread starvation, NullPointerException) and analyze why this specific logic failure triggered. Cite missing keywords or parameter errors if visible.

### 3. How to Fix It
Provide detailed, actionable code blocks, database queries, or server flags to resolve the problem.
"""
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": f"You are a helpful system engineer running in {mode} feedback mode."},
                {"role": "user", "content": prompt}
            ],
            model=self.model,
            temperature=0.15
        )
        return response.choices[0].message.content

    def fix_code_files(self, log_context: str, files_data: dict) -> dict:
        """Uses Groq to trace and rewrite buggy workspace files based on logs."""
        api_key = get_api_key()
        client = Groq(api_key=api_key)

        prompt = f"""
You are an expert debugger. You are given a system log error context and some project files.
Analyze the logs, find which file has the bug causing this error, and fix the code inside that file.

[LOG CONTEXT]
{log_context}
[/LOG CONTEXT]

Here are the workspace files:
{json.dumps(files_data, indent=2)}

Please output the corrected version of the files in a JSON format matching this exact structure:
{{
  "file_name_that_was_fixed.ext": "full corrected code content here"
}}
Return ONLY valid JSON. No conversational text. No markdown formatting outside of JSON.
"""
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are an automated code generator. You speak only in raw JSON matching the requested payload schema."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)