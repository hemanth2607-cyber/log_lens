// frontend/src/App.jsx
import React, { useState, useEffect } from 'react';
import { Terminal, Play, Trash2, Key, AlertTriangle, Cpu, Loader, ShieldAlert, Download, FolderGit2, Eye, CpuIcon, CheckCircle } from 'lucide-react';
import { marked } from 'marked';

export default function App() {
  const [apiKeyStatus, setApiKeyStatus] = useState({ is_configured: false, masked_key: null });
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [rawLogs, setRawLogs] = useState('');
  
  const [workspaceFiles, setWorkspaceFiles] = useState([]);
  const [diagnosticMode, setDiagnosticMode] = useState('general');
  
  const [status, setStatus] = useState('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [diagnosticResult, setDiagnosticResult] = useState(null);
  const [activeAnomalyIndex, setActiveAnomalyIndex] = useState(0);

  const [fixStatus, setFixStatus] = useState('idle');
  const [downloadId, setDownloadId] = useState(null);
  const [modifiedFiles, setModifiedFiles] = useState([]);

  useEffect(() => {
    fetchConfigStatus();
  }, []);

  const fetchConfigStatus = async () => {
    try {
      const res = await fetch('/api/config');
      const data = await res.json();
      setApiKeyStatus(data);
    } catch (err) {
      console.error('Failed to parse API configurations:', err);
    }
  };

  const handleSaveKey = async () => {
    if (!apiKeyInput.trim()) return;
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ groq_api_key: apiKeyInput.trim() }),
      });
      const data = await res.json();
      if (data.status === 'success') {
        alert('Groq key successfully persisted.');
        setApiKeyInput('');
        fetchConfigStatus();
      }
    } catch (err) {
      alert('Key persistence transaction failed.');
    }
  };

  const handleLogFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      setRawLogs(evt.target.result);
    };
    reader.readAsText(file);
  };

  const handleWorkspaceUpload = (e) => {
    const files = Array.from(e.target.files);
    setWorkspaceFiles(files);
  };

  // ADVANCED STITCHED MULTI-ANOMALY PRE-SLICER
  const preSliceLogs = (text) => {
    const lines = text.split('\n');
    const totalLines = lines.length;
    
    // Only pre-slice if the file is moderately large (> 1,000 lines)
    if (totalLines <= 1000) {
      return text;
    }

    const anomalyPattern = /\b(ERROR|CRITICAL|FATAL|EXCEPTION|SEVERE|FAIL)\b/i;
    const errorIndices = [];

    // 1. Locate all error occurrences throughout the 100,000 lines
    for (let i = 0; i < totalLines; i++) {
      if (anomalyPattern.test(lines[i])) {
        errorIndices.push(i);
      }
    }

    if (errorIndices.length === 0) {
      return text;
    }

    // 2. Group closely occurring error indices (within 30 lines) to avoid overlapping slices
    const groups = [];
    let currentGroup = [errorIndices[0]];

    for (let i = 1; i < errorIndices.length; i++) {
      if (errorIndices[i] - currentGroup[currentGroup.length - 1] <= 30) {
        currentGroup.push(errorIndices[i]);
      } else {
        groups.push(currentGroup);
        currentGroup = [errorIndices[i]];
      }
    }
    groups.push(currentGroup);

    // Limit to top 5 distinct anomaly groups to optimize API speeds
    const targetGroups = groups.slice(0, 5);

    // 3. Extract ±50 lines around each distinct group and stitch them together
    const stitchedLines = [];
    targetGroups.forEach((group) => {
      const anchorIndex = group[0];
      const start = Math.max(0, anchorIndex - 50);
      const end = Math.min(totalLines, anchorIndex + 51);
      
      for (let i = start; i < end; i++) {
        stitchedLines.push(lines[i]);
      }
    });

    return stitchedLines.join('\n');
  };

  const runAnalysis = async () => {
    if (!rawLogs.trim()) {
      alert('Log entries cannot be empty.');
      return;
    }
    setStatus('loading');
    setErrorMessage('');
    setDiagnosticResult(null);
    setFixStatus('idle');
    setDownloadId(null);
    setModifiedFiles([]);
    
    // Execute multi-sector pre-slicing
    const optimizedLogs = preSliceLogs(rawLogs);

    const formData = new FormData();
    const logsBlob = new Blob([optimizedLogs], { type: 'text/plain' });
    formData.append('raw_logs', logsBlob, 'uploaded_logs.log');
    
    formData.append('mode', diagnosticMode);
    workspaceFiles.forEach((file) => {
      formData.append('workspace_files', file);
    });

    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Service processing failure.');
      }

      const data = await res.json();
      setDiagnosticResult(data);
      setStatus('success');
    } catch (err) {
      setErrorMessage(err.message);
      setStatus('error');
    }
  };

  const runCodeFix = async () => {
    if (workspaceFiles.length === 0) {
      alert('Please upload your workspace source files first.');
      return;
    }
    setFixStatus('processing');
    
    const optimizedLogs = preSliceLogs(rawLogs);

    const formData = new FormData();
    const logsBlob = new Blob([optimizedLogs], { type: 'text/plain' });
    formData.append('raw_logs', logsBlob, 'uploaded_logs.log');
    
    workspaceFiles.forEach((file) => {
      formData.append('workspace_files', file);
    });

    try {
      const res = await fetch('/api/fix-code', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Codebase fix failed.');
      }
      const data = await res.json();
      setDownloadId(data.download_id);
      setModifiedFiles(data.modified_files || []);
      setFixStatus('fixed');
    } catch (err) {
      alert(err.message);
      setFixStatus('idle');
    }
  };

  const anomaliesList = diagnosticResult?.anomalies || [];
  const activeAnomaly = anomaliesList[activeAnomalyIndex] || null;

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-ice-100 via-sky-100/50 to-blue-200/40">
      
      {/* HEADER NAVBAR */}
      <header className="bg-gradient-to-r from-ice-900 via-ice-800 to-sky-950 border-b border-ice-700 sticky top-0 z-50 shadow-md">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-3.5">
            <div className="p-1.5 bg-white/10 rounded-xl border border-white/20 flex items-center justify-center shadow-inner">
              <img 
                src="/logo.png" 
                onError={(e) => {
                  e.target.style.display = 'none';
                  e.target.nextSibling.style.display = 'block';
                }}
                className="w-10 h-10 rounded-lg object-cover" 
                alt="Logo"
              />
              <div style={{display: 'none'}} className="p-1.5 text-white">
                <Terminal className="w-7 h-7" />
              </div>
            </div>
            <div>
              <h1 className="text-lg font-black text-white tracking-tight flex items-center gap-1.5">Log Lens</h1>
              <p className="text-[10px] text-ice-200 font-bold uppercase tracking-widest">Workspace Diagnostics & Automated Repair</p>
            </div>
          </div>

          <div className="flex items-center space-x-2 bg-black/20 p-1 rounded-xl border border-white/10">
            <Key className="w-3.5 h-3.5 text-ice-300 ml-2" />
            <input
              type="password"
              placeholder={apiKeyStatus.is_configured ? `Active Key: ${apiKeyStatus.masked_key}` : 'Configure Groq API Key'}
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
              className="bg-transparent border-0 text-xs px-2 py-1 focus:outline-none w-48 text-white placeholder-ice-300/60"
            />
            <button
              onClick={handleSaveKey}
              className="bg-ice-600 hover:bg-ice-500 text-white text-[11px] font-bold px-3 py-1.5 rounded-lg transition duration-150 shadow-md"
            >
              Save
            </button>
          </div>
        </div>
      </header>

      {/* CORE WORKSPACE */}
      <main className="max-w-7xl mx-auto px-4 py-6 flex-grow grid grid-cols-1 md:grid-cols-12 gap-6 w-full items-stretch">
        
        {/* Left Control Column */}
        <section className="md:col-span-5 flex flex-col space-y-4">
          
          {/* Logs Inputs Box */}
          <div className="bg-gradient-to-b from-ice-50/90 to-white/95 border border-ice-200/80 rounded-xl shadow-md flex flex-col overflow-hidden">
            <div className="flex items-center justify-between bg-gradient-to-r from-ice-100 to-ice-50/30 border-b border-ice-200 px-4 py-2.5">
              <h2 className="font-extrabold text-slate-900 text-xs tracking-wider uppercase">System Logs</h2>
              <label className="text-[10px] bg-ice-600 hover:bg-ice-700 text-white font-extrabold px-2.5 py-1 rounded-md cursor-pointer transition shadow-sm">
                Upload .log
                <input type="file" accept=".log, .txt" onChange={handleLogFileUpload} className="hidden" />
              </label>
            </div>
            <div className="p-4">
              <textarea
                value={rawLogs}
                onChange={(e) => setRawLogs(e.target.value)}
                placeholder="Paste system logs here..."
                className="w-full h-32 p-3 bg-white border border-ice-100 rounded-lg text-xs font-mono text-slate-700 focus:outline-none focus:ring-2 focus:ring-ice-500 focus:border-transparent resize-none leading-relaxed shadow-inner"
              />
            </div>
          </div>

          {/* Project Source Files Box */}
          <div className="bg-gradient-to-b from-ice-50/90 to-white/95 border border-ice-200/80 rounded-xl shadow-md flex flex-col overflow-hidden">
            <div className="flex items-center justify-between bg-gradient-to-r from-ice-100 to-ice-50/30 border-b border-ice-200 px-4 py-2.5">
              <h2 className="font-extrabold text-slate-900 text-xs tracking-wider uppercase flex items-center gap-1.5">
                <FolderGit2 className="w-3.5 h-3.5 text-ice-600" />
                <span>Source Files (Workspace)</span>
              </h2>
              <label className="text-[10px] bg-ice-600 hover:bg-ice-700 text-white font-extrabold px-2.5 py-1 rounded-md cursor-pointer transition shadow-sm">
                Select Files
                <input type="file" multiple onChange={handleWorkspaceUpload} className="hidden" />
              </label>
            </div>
            <div className="p-4">
              <div className="bg-white border border-dashed border-ice-200 rounded-lg p-3 text-center min-h-[80px] flex flex-col items-center justify-center shadow-inner">
                {workspaceFiles.length === 0 ? (
                  <p className="text-slate-400 text-[11px] leading-relaxed max-w-[240px]">No files uploaded. Select source files to enable auto-fixing.</p>
                ) : (
                  <div className="w-full text-left">
                    <p className="text-slate-700 text-[11px] font-bold mb-1">Uploaded ({workspaceFiles.length}):</p>
                    <ul className="text-[10px] font-mono text-slate-500 max-h-16 overflow-y-auto space-y-1 bg-slate-50 p-1.5 border border-slate-100 rounded">
                      {workspaceFiles.map((file, idx) => (
                        <li key={idx} className="truncate">📁 {file.name}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Options and Action Button */}
          <div className="bg-gradient-to-b from-ice-50/90 to-white/95 border border-ice-200/80 rounded-xl p-4 shadow-md flex flex-col space-y-3">
            <div>
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 block mb-1.5">Diagnostic Format</span>
              <div className="grid grid-cols-2 gap-2 bg-ice-100/50 p-1 rounded-lg border border-ice-100/80">
                <button
                  onClick={() => setDiagnosticMode('general')}
                  className={`py-1.5 rounded font-bold text-xs transition duration-150 flex items-center justify-center gap-1 ${
                    diagnosticMode === 'general' ? 'bg-white text-ice-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <Eye className="w-3 h-3" />
                  General
                </button>
                <button
                  onClick={() => setDiagnosticMode('technical')}
                  className={`py-1.5 rounded font-bold text-xs transition duration-150 flex items-center justify-center gap-1 ${
                    diagnosticMode === 'technical' ? 'bg-white text-ice-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <CpuIcon className="w-3 h-3" />
                  Technical
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between pt-1">
              <button
                onClick={() => { setRawLogs(''); setWorkspaceFiles([]); }}
                className="text-slate-400 hover:text-slate-600 font-bold text-xs transition flex items-center gap-1"
              >
                <Trash2 className="w-3 h-3" />
                Reset
              </button>
              
              <button
                onClick={runAnalysis}
                className="bg-gradient-to-r from-ice-600 to-sky-600 hover:from-ice-700 hover:to-sky-700 text-white font-extrabold text-xs px-5 py-2.5 rounded-lg transition shadow-[0_4px_12px_0_rgba(14,165,233,0.3)] hover:shadow-lg flex items-center space-x-1.5"
              >
                <Play className="w-3.5 h-3.5" />
                <span>Run Diagnostics</span>
              </button>
            </div>
          </div>
        </section>

        {/* Right Output Column */}
        <section className="md:col-span-7 flex flex-col h-full">
          <div className="bg-gradient-to-b from-ice-50/90 to-white/95 border border-ice-200/80 rounded-xl shadow-md flex flex-col h-full min-h-[500px] overflow-hidden">
            
            {/* IDLE STATE */}
            {status === 'idle' && (
              <div className="flex-grow flex flex-col items-center justify-center p-6 text-center my-auto">
                <div className="p-3.5 bg-ice-50 rounded-xl text-ice-500 mb-3 shadow-sm border border-ice-100">
                  <Cpu className="w-7 h-7" />
                </div>
                <h3 className="text-slate-900 font-extrabold text-xs uppercase tracking-wider mb-1">Awaiting Data</h3>
                <p className="text-slate-400 text-[11px] max-w-xs leading-relaxed">
                  Provide logs and files on the left-hand panel, then execute diagnostics to review errors.
                </p>
              </div>
            )}

            {/* PROCESSING/LOADING STATE */}
            {status === 'loading' && (
              <div className="flex-grow flex flex-col items-center justify-center p-6 text-center my-auto">
                <Loader className="w-8 h-8 text-ice-500 animate-spin mb-3" />
                <h3 className="text-slate-900 font-bold text-xs uppercase tracking-wider mb-1">Executing Analysis</h3>
                <p className="text-slate-400 text-[11px] max-w-xs leading-relaxed animate-pulse">
                  Scanning log files, compiling stack trace variables, and generating code correlation models...
                </p>
              </div>
            )}

            {/* ERROR PRESENTATION */}
            {status === 'error' && (
              <div className="flex-grow flex flex-col items-center justify-center p-6 text-center my-auto">
                <div className="p-3 bg-rose-50 rounded-xl text-rose-500 mb-3 border border-rose-100">
                  <ShieldAlert className="w-7 h-7" />
                </div>
                <h3 className="text-slate-900 font-bold text-xs uppercase tracking-wider mb-1">Analysis Aborted</h3>
                <p className="text-rose-600 text-[11px] max-w-xs leading-relaxed bg-rose-50/70 p-2.5 rounded-lg border border-rose-100 font-medium">
                  {errorMessage}
                </p>
                <button onClick={() => setStatus('idle')} className="mt-4 text-[11px] font-bold text-ice-600 hover:text-ice-700">
                  Return to Workspace
                </button>
              </div>
            )}

            {/* DETAILED RESULTS DASHBOARD */}
            {status === 'success' && activeAnomaly && (
              <div className="flex flex-col h-full divide-y divide-ice-100 overflow-hidden">
                
                {/* Multi-Error Tab Bar Selector */}
                {anomaliesList.length > 1 && (
                  <div className="bg-ice-50/50 px-4 py-2 flex items-center border-b border-ice-100 overflow-x-auto shrink-0">
                    <span className="text-[9px] font-extrabold uppercase tracking-wider text-slate-500 mr-3 shrink-0">
                      Issues ({anomaliesList.length}):
                    </span>
                    <div className="flex space-x-1.5">
                      {anomaliesList.map((anomaly, idx) => (
                        <button
                          key={anomaly.anomaly_id}
                          onClick={() => { setActiveAnomalyIndex(idx); setFixStatus('idle'); setDownloadId(null); }}
                          className={`text-[10px] px-2.5 py-1 rounded font-bold transition duration-150 shrink-0 ${
                            activeAnomalyIndex === idx
                              ? 'bg-ice-600 text-white shadow-sm'
                              : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'
                          }`}
                        >
                          Err #{anomaly.anomaly_id}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Slices Window Visualization */}
                <div className="p-4 bg-ice-50/10 shrink-0">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-slate-950 font-extrabold text-[10px] tracking-wider uppercase">
                      Log Snippet View (±5 Lines)
                    </h3>
                    <span className="bg-rose-100 text-rose-700 text-[9px] font-extrabold px-2 py-0.5 rounded-full flex items-center gap-1 border border-rose-200">
                      <AlertTriangle className="w-2.5 h-2.5" />
                      Line {activeAnomaly.anomaly_line}
                    </span>
                  </div>

                  <div className="bg-slate-900 text-slate-300 font-mono text-[10px] p-3 rounded-lg overflow-y-auto h-36 space-y-1 shadow-inner border border-slate-950 leading-relaxed">
                    {(activeAnomaly.lines || []).map((line) => (
                      <div
                        key={line.line_number}
                        className={`flex py-0.5 px-2 rounded transition duration-150 ${
                          line.is_error
                            ? 'bg-rose-950/65 text-rose-200 border-l-4 border-rose-500 font-semibold shadow-sm'
                            : 'hover:bg-slate-800/40'
                        }`}
                      >
                        <span className="text-slate-500 text-right select-none pr-3 w-6 shrink-0">
                          {line.line_number}
                        </span>
                        <span className="whitespace-pre-wrap break-all">{line.content}</span>
                      </div>
                    ))}
                  </div>

                  {activeAnomaly.matched_file && (
                    <div className="mt-2 bg-emerald-50 text-emerald-800 text-[10px] font-bold px-2.5 py-1.5 rounded border border-emerald-100 flex items-center justify-between">
                      <span>✓ Mapped error traceback to workspace source file: {activeAnomaly.matched_file}</span>
                    </div>
                  )}
                </div>

                {/* SRE Explanation Block */}
                <div className="p-4 overflow-y-auto flex-grow max-h-[220px]">
                  <h3 className="text-slate-950 font-extrabold text-[10px] tracking-wider uppercase mb-2">
                    Diagnostic Report ({diagnosticMode === 'general' ? 'General' : 'Technical'})
                  </h3>
                  <div
                    className="prose prose-sm prose-slate max-w-none text-slate-700 leading-relaxed text-xs space-y-3"
                    dangerouslySetInnerHTML={{ __html: marked.parse(activeAnomaly.report || '') }}
                  />
                </div>

                {/* Auto Code Fix Dashboard Drawer */}
                {workspaceFiles.length > 0 && (
                  <div className="bg-ice-100/20 p-4 border-t border-ice-100 flex flex-col space-y-3 shrink-0">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="font-extrabold text-slate-950 text-[10px] uppercase tracking-wider">Automated Code Correction</h4>
                        <p className="text-[10px] text-slate-500">Compile automated code patch in Groq.</p>
                      </div>
                      
                      {fixStatus === 'idle' && (
                        <button
                          onClick={runCodeFix}
                          className="bg-emerald-600 hover:bg-emerald-500 text-white font-extrabold text-xs px-4 py-2 rounded-lg transition shadow-[0_4px_12px_0_rgba(16,185,129,0.3)] hover:shadow-lg"
                        >
                          Auto-Fix Source Code
                        </button>
                      )}

                      {fixStatus === 'processing' && (
                        <div className="flex items-center space-x-1.5 text-emerald-700 text-xs font-bold">
                          <Loader className="w-3.5 h-3.5 animate-spin" />
                          <span>Patching...</span>
                        </div>
                      )}
                    </div>

                    {fixStatus === 'fixed' && (
                      <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2.5">
                        <div>
                          <p className="text-emerald-900 font-bold text-xs flex items-center gap-1.5">
                            <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
                            Code Patch Built successfully
                          </p>
                          <p className="text-[10px] text-emerald-600 mt-0.5">Modified: {(modifiedFiles || []).join(', ')}</p>
                        </div>
                        <a
                          href={`/api/download/${downloadId}`}
                          className="bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs px-4 py-2 rounded-lg transition shadow-md flex items-center justify-center gap-1"
                        >
                          <Download className="w-3.5 h-3.5" />
                          Download Zip
                        </a>
                      </div>
                    )}
                  </div>
                )}

              </div>
            )}

          </div>
        </section>

      </main>

      <footer className="bg-white border-t border-ice-100 mt-auto py-2.5 text-center text-slate-400 text-[10px] font-semibold shrink-0">
        Log Lens — Engineered Full-Stack Agent Model
      </footer>
    </div>
  );
}