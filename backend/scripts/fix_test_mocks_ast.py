import os
import ast

TEST_DIR = "tests"

def fix_all():
    for root, _, files in os.walk(TEST_DIR):
        for file in files:
            if not file.endswith(".py"): continue
            filepath = os.path.join(root, file)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue

            insertions = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    kwargs = {kw.arg: kw for kw in node.keywords if kw.arg}
                    
                    added_args = []
                    if node.func.id == "EnterpriseProfile":
                        if "organization_name" not in kwargs: added_args.append('organization_name="Test Org"')
                        if "industry_sector" not in kwargs: added_args.append('industry_sector="Finance"')
                    elif node.func.id == "Regulation":
                        if "publication_date" not in kwargs: added_args.append('publication_date=datetime.date(2026,1,1)')
                        if "sector" not in kwargs: added_args.append('sector="Test"')
                        if "region" not in kwargs: added_args.append('region="Test"')
                        if "content_text" not in kwargs: added_args.append('content_text="Test"')
                        if "title" not in kwargs: added_args.append('title="Test"')
                        if "authority" not in kwargs: added_args.append('authority="Test"')
                    elif node.func.id == "DocumentVersion":
                        if "content_text" not in kwargs: added_args.append('content_text="Test"')
                        if "publication_date" not in kwargs: added_args.append('publication_date=datetime.date(2026,1,1)')
                    elif node.func.id == "RegulatoryApplicabilityAssessment":
                        if "rationale" not in kwargs: added_args.append('rationale="Test"')
                    elif node.func.id == "RegulatoryObligation":
                        if "source_citation" not in kwargs: added_args.append('source_citation="Test"')
                        if "title" not in kwargs: added_args.append('title="Test"')
                        if "description" not in kwargs: added_args.append('description="Test"')
                        if "obligation_code" not in kwargs: added_args.append('obligation_code="OBL-1"')
                        if "obligation_type" not in kwargs: added_args.append('obligation_type="REPORTING"')
                    elif node.func.id == "ComplianceTask":
                        if "assignee" not in kwargs: added_args.append('assignee="Test Assignee"')
                        if "reviewer" not in kwargs: added_args.append('reviewer="Test Reviewer"')
                        if "title" not in kwargs: added_args.append('title="Test"')
                    
                    if added_args:
                        insertions.append((node.end_lineno, node.end_col_offset, added_args))

            if insertions:
                lines = content.splitlines()
                # Apply in reverse order to not mess up offsets
                insertions.sort(key=lambda x: (x[0], x[1]), reverse=True)
                for end_line, end_col, args in insertions:
                    line_idx = end_line - 1
                    line = lines[line_idx]
                    
                    if line[end_col-1] == ')':
                        prefix = ", " if line[end_col-2] != '(' else ""
                        lines[line_idx] = line[:end_col-1] + prefix + ", ".join(args) + line[end_col-1:]

                new_content = "\n".join(lines) + "\n"
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Patched {filepath}")

fix_all()
