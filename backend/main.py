# backend/main.py
import io
import uuid
import zipfile
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from parser import LogSlicer
from explainer import ExplainerService
from config import load_config, save_config, get_api_key

app = FastAPI(title="Log Anomaly Explainer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ZIP_SESSION_CACHE: Dict[str, bytes] = {}

class ConfigPayload(BaseModel):
    groq_api_key: str

@app.get("/api/config")
def get_config():
    api_key = get_api_key()
    return {
        "is_configured": bool(api_key),
        "masked_key": f"{api_key[:6]}...{api_key[-4:]}" if api_key else None
    }

@app.post("/api/config")
def update_config(payload: ConfigPayload):
    config = load_config()
    config["groq_api_key"] = payload.groq_api_key.strip()
    save_config(config)
    return {"status": "success", "message": "API key successfully updated."}


@app.post("/api/analyze")
async def analyze_logs(
    raw_logs: UploadFile = File(...),  # Changed from Form to UploadFile
    mode: str = Form("general"),
    workspace_files: List[UploadFile] = File([])
):
    # Read the log stream safely
    log_bytes = await raw_logs.read()
    raw_logs_str = log_bytes.decode("utf-8", errors="ignore")

    workspace_map = {}
    for w_file in workspace_files:
        content = await w_file.read()
        workspace_map[w_file.filename] = content.decode("utf-8", errors="ignore")

    slicer = LogSlicer()
    ui_anomalies = slicer.slice_logs(raw_logs_str, context_size=5)
    ai_anomalies = slicer.slice_logs(raw_logs_str, context_size=20)
    
    if not ui_anomalies:
        raise HTTPException(
            status_code=422,
            detail="No error indicators found in log data."
        )

    service = ExplainerService()
    results = []
    
    for idx, anomaly in enumerate(ui_anomalies[:5]):
        ai_anomaly = ai_anomalies[idx] if idx < len(ai_anomalies) else anomaly
        formatted_rows = []
        for line in ai_anomaly["lines"]:
            prefix = "--> " if line["is_error"] else "    "
            formatted_rows.append(f"{prefix}{line['line_number']}: {line['content']}")
        ai_context_str = "\n".join(formatted_rows)

        matched_code = ""
        matched_filename = ""
        for ref_file in anomaly["referenced_files"]:
            if ref_file in workspace_map:
                matched_code = workspace_map[ref_file]
                matched_filename = ref_file
                break

        try:
            report = service.analyze(anomaly["anomaly_line"], ai_context_str, mode=mode, matched_code=matched_code)
            results.append({
                "anomaly_id": anomaly["anomaly_id"],
                "anomaly_line": anomaly["anomaly_line"],
                "preview": anomaly["preview"],
                "lines": anomaly["lines"],
                "matched_file": matched_filename,
                "report": report
            })
        except Exception as ex:
            results.append({
                "anomaly_id": anomaly["anomaly_id"],
                "anomaly_line": anomaly["anomaly_line"],
                "preview": anomaly["preview"],
                "lines": anomaly["lines"],
                "report": f"### Error\nAnalysis engine failure: {str(ex)}"
            })
            
    return {"anomalies": results}


@app.post("/api/fix-code")
async def fix_code(
    raw_logs: UploadFile = File(...),  # Changed from Form to UploadFile
    workspace_files: List[UploadFile] = File(...)
):
    if not workspace_files:
        raise HTTPException(status_code=400, detail="No source files were provided.")

    log_bytes = await raw_logs.read()
    raw_logs_str = log_bytes.decode("utf-8", errors="ignore")

    workspace_map = {}
    for w_file in workspace_files:
        content = await w_file.read()
        workspace_map[w_file.filename] = content.decode("utf-8", errors="ignore")

    slicer = LogSlicer()
    anomalies = slicer.slice_logs(raw_logs_str, context_size=20)
    
    target_workspace = {}
    matched_filename = None
    
    if anomalies:
        for ref_file in anomalies[0]["referenced_files"]:
            if ref_file in workspace_map:
                matched_filename = ref_file
                target_workspace = {ref_file: workspace_map[ref_file]}
                break
                
    if not target_workspace:
        target_workspace = workspace_map

    formatted_rows = []
    if anomalies:
        for line in anomalies[0]["lines"]:
            prefix = "--> " if line["is_error"] else "    "
            formatted_rows.append(f"{prefix}{line['line_number']}: {line['content']}")
    log_context_str = "\n".join(formatted_rows)

    service = ExplainerService()
    try:
        fixed_files = service.fix_code_files(log_context_str, target_workspace)
        
        if not isinstance(fixed_files, dict):
            fixed_files = {}
        if "fixed_files" in fixed_files and isinstance(fixed_files["fixed_files"], dict):
            fixed_files = fixed_files["fixed_files"]

        final_codebase = {**workspace_map, **fixed_files}

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for filename, file_content in final_codebase.items():
                zip_file.writestr(filename, file_content)

        zip_buffer.seek(0)
        session_id = str(uuid.uuid4())
        ZIP_SESSION_CACHE[session_id] = zip_buffer.getvalue()

        return {
            "status": "success",
            "download_id": session_id,
            "modified_files": list(fixed_files.keys()) if fixed_files else [matched_filename or "FixedFile"]
        }

    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Code generation failed: {str(ex)}")


@app.get("/api/download/{download_id}")
def download_fixed_zip(download_id: str):
    zip_data = ZIP_SESSION_CACHE.get(download_id)
    if not zip_data:
        raise HTTPException(status_code=404, detail="Download session expired or not found.")
        
    return StreamingResponse(
        io.BytesIO(zip_data),
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": f"attachment; filename=fixed_source_code.zip"}
    )