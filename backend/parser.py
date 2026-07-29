# backend/parser.py
import re
from typing import Optional, Dict, Any, List

class LogSlicer:
    """Scans logs, segregates high-volume inputs, and restores original absolute line numbers."""
    def __init__(self, pre_context: int = 5, post_context: int = 5, merge_threshold: int = 10, chunk_size: int = 1024):
        self.pre_context = pre_context
        self.post_context = post_context
        self.merge_threshold = merge_threshold  
        self.chunk_size = chunk_size  
        self.pattern = re.compile(
            r'\b(ERROR|CRITICAL|FATAL|EXCEPTION|SEVERE|FAIL)\b', 
            re.IGNORECASE
        )
        self.file_trace_pattern = re.compile(r'([a-zA-Z0-9_\-]+\.(java|py|js|ts|cpp|go|cs))', re.IGNORECASE)
        # Pattern to match absolute line prefix (e.g., "25400:")
        self.prefix_pattern = re.compile(r'^(\d+):')

    def slice_logs(self, raw_text: str, context_size: int = 5) -> List[Dict[str, Any]]:
        lines = raw_text.splitlines()
        total_lines = len(lines)
        error_indices = []
        
        if total_lines > self.chunk_size:
            segments = [lines[i:i + self.chunk_size] for i in range(0, total_lines, self.chunk_size)]
            for seg_idx, segment in enumerate(segments):
                offset = seg_idx * self.chunk_size
                for idx, line in enumerate(segment):
                    if self.pattern.search(line):
                        error_indices.append(offset + idx)
        else:
            for idx, line in enumerate(lines):
                if self.pattern.search(line):
                    error_indices.append(idx)
                
        if not error_indices:
            return []
            
        groups = []
        current_group = [error_indices[0]]
        
        for idx in error_indices[1:]:
            if idx - current_group[-1] <= self.merge_threshold:
                current_group.append(idx)
            else:
                groups.append(current_group)
                current_group = [idx]
        groups.append(current_group)
        
        anomalies = []
        for group_idx, g in enumerate(groups, start=1):
            target_idx = g[0]
            
            start_idx = max(0, target_idx - context_size)
            end_idx = min(len(lines), target_idx + context_size + 1)
            
            # Retrieve the absolute line number from prefix, if available
            absolute_anomaly_line = target_idx + 1
            line_match = self.prefix_pattern.match(lines[target_idx])
            if line_match:
                absolute_anomaly_line = int(line_match.group(1))

            sliced_lines = []
            referenced_files = set()
            
            for i in range(start_idx, end_idx):
                line_content = lines[i]
                display_line_num = i + 1
                
                # Check for absolute line number prefix in current line
                line_match = self.prefix_pattern.match(line_content)
                if line_match:
                    display_line_num = int(line_match.group(1))
                    # Strip the raw prefix "25400: " for a clean log terminal visual
                    line_content = re.sub(r'^\d+:\s*', '', line_content)

                sliced_lines.append({
                    "line_number": display_line_num,
                    "content": line_content,
                    "is_error": (i in g)
                })
                
                # Search for source code file references in the cleaned content
                matches = self.file_trace_pattern.findall(line_content)
                for m in matches:
                    referenced_files.add(m[0])
                
            anomalies.append({
                "anomaly_id": group_idx,
                "anomaly_line": absolute_anomaly_line,
                "preview": lines[target_idx][:80].strip(),
                "lines": sliced_lines,
                "referenced_files": list(referenced_files)
            })
            
        return anomalies