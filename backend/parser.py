# backend/parser.py
import re
from typing import Optional, Dict, Any, List

class LogSlicer:
    """Scans logs, segregates high-volume files into 1,024-line chunks, and clusters errors."""
    def __init__(self, pre_context: int = 5, post_context: int = 5, merge_threshold: int = 10, chunk_size: int = 1024):
        self.pre_context = pre_context
        self.post_context = post_context
        self.merge_threshold = merge_threshold  
        self.chunk_size = chunk_size  # Segment threshold set to exactly 1024
        self.pattern = re.compile(
            r'\b(ERROR|CRITICAL|FATAL|EXCEPTION|SEVERE|FAIL)\b', 
            re.IGNORECASE
        )
        self.file_trace_pattern = re.compile(r'([a-zA-Z0-9_\-]+\.(java|py|js|ts|cpp|go|cs))', re.IGNORECASE)

    def slice_logs(self, raw_text: str, context_size: int = 5) -> List[Dict[str, Any]]:
        lines = raw_text.splitlines()
        total_lines = len(lines)
        error_indices = []
        
        # 1. Dynamic Segregation (Triggered for files above 1,024 lines)
        if total_lines > self.chunk_size:
            # Segregate the log array into multiple 1,024-line segments
            segments = [lines[i:i + self.chunk_size] for i in range(0, total_lines, self.chunk_size)]
            
            for seg_idx, segment in enumerate(segments):
                # Calculate the line index offset for this segment
                offset = seg_idx * self.chunk_size
                
                # Scan this segment efficiently
                for idx, line in enumerate(segment):
                    if self.pattern.search(line):
                        error_indices.append(offset + idx)
        else:
            # Single-pass standard scanning for smaller files
            for idx, line in enumerate(lines):
                if self.pattern.search(line):
                    error_indices.append(idx)
                
        if not error_indices:
            return []
            
        # 2. Group closely occurring error lines globally
        groups = []
        current_group = [error_indices[0]]
        
        for idx in error_indices[1:]:
            if idx - current_group[-1] <= self.merge_threshold:
                current_group.append(idx)
            else:
                groups.append(current_group)
                current_group = [idx]
        groups.append(current_group)
        
        # 3. Create context slices for each independent error group
        anomalies = []
        for group_idx, g in enumerate(groups, start=1):
            target_idx = g[0]
            
            start_idx = max(0, target_idx - context_size)
            end_idx = min(len(lines), target_idx + context_size + 1)
            
            sliced_lines = []
            referenced_files = set()
            
            for i in range(start_idx, end_idx):
                sliced_lines.append({
                    "line_number": i + 1,
                    "content": lines[i],
                    "is_error": (i in g)
                })
                matches = self.file_trace_pattern.findall(lines[i])
                for m in matches:
                    referenced_files.add(m[0])
                
            anomalies.append({
                "anomaly_id": group_idx,
                "anomaly_line": target_idx + 1,
                "preview": lines[target_idx][:80].strip(),
                "lines": sliced_lines,
                "referenced_files": list(referenced_files)
            })
            
        return anomalies