import re
import json

INPUT_JSON = "integrated_output_with_text.json"
OUTPUT_JSON = "integrated_output_with_tables.json"

NUMERIC = re.compile(r"\d[\d,]*")

def parse_financial_table(section_text):
    lines = [l.strip() for l in section_text.splitlines() if l.strip()]
    rows = []

    for line in lines:
        nums = NUMERIC.findall(line)
        if len(nums) >= 4:
            # Heuristic: [item][note][g24][g23][c24][c23]
            parts = re.split(r"\s{2,}|\t", line)

            if len(parts) < 6:
                continue

            row = {
                "item": parts[0],
                "note": parts[1] if parts[1].isdigit() else None,
                "group_2024": parts[-4],
                "group_2023": parts[-3],
                "company_2024": parts[-2],
                "company_2023": parts[-1],
            }
            rows.append(row)

    return rows


with open(INPUT_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)

for section in data["document_structure"]["sections"]:
    text = section.get("text", "")
    if "Statements of Financial Position" in section["title"]:
        table = {
            "type": "financial_statement",
            "statement": "Statement of Financial Position",
            "currency": "Rs.'000",
            "columns": [
                "Item",
                "Note",
                "Group_2024",
                "Group_2023",
                "Company_2024",
                "Company_2023"
            ],
            "rows": parse_financial_table(text)
        }
        section["tables"] = [table]

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("Structured table reconstruction complete.")
