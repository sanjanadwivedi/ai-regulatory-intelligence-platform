import json
import os
import glob
from pathlib import Path

# The log files
log_files = glob.glob(r'C:\Users\sanja\.gemini\antigravity-ide\brain\*\.system_generated\logs\transcript_full.jsonl')

files_content = {}

for log_file in log_files:
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                except:
                    continue
                
                if 'tool_calls' in data:
                    for call in data['tool_calls']:
                        if call.get('name') == 'write_to_file':
                            args = call.get('args', {})
                            target = args.get('TargetFile', '')
                            if 'backend\\tests\\' in target or 'backend/tests/' in target:
                                content = args.get('CodeContent', '')
                                files_content[target] = content
                                print(f"Found initial write for {target}")
                        
                        elif call.get('name') == 'replace_file_content':
                            args = call.get('args', {})
                            target = args.get('TargetFile', '')
                            if 'backend\\tests\\' in target or 'backend/tests/' in target:
                                # Not perfect, but we keep track of replacements if we want full recovery
                                print(f"Found replace for {target}")
                                # To get the absolute latest file state, maybe we should also look for view_file outputs!
                
                # Check tool output for view_file
                if data.get('type') == 'TOOL_RESPONSE':
                    tool_calls = data.get('tool_calls', []) # Wait, TOOL_RESPONSE doesn't have tool_calls, it has content?
                    # Let's check 'content' or 'output'
                    pass
    except Exception as e:
        print(f"Error parsing {log_file}: {e}")

# Output recovered info
print(f"\nRecovered {len(files_content)} files.")
for t, c in files_content.items():
    print(f"Target: {t} - Size: {len(c)}")
    # We can write them out directly
    out_path = Path(t)
    if 'backend' in out_path.parts:
        try:
            # Reconstruct the real path relative to project
            # but let's just write them to a temp folder first
            tmp_path = Path("recovered_tests") / out_path.name
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(c, encoding='utf-8')
            print(f"Written to {tmp_path}")
        except Exception as e:
            print(f"Failed writing {t}: {e}")

