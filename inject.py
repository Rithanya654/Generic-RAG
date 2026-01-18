import json

INPUT_JSON = "integrated_output.json"
OUTPUT_JSON = "integrated_output_with_text.json"

with open(INPUT_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)

# --- Correct paths ---
sections = data["document_structure"]["sections"]
pages = data["pages"]

# --- Build page_number → text map ---
page_text = {}

for page in pages:
    pno = page.get("page_number")
    text_chunks = []

    for el in page.get("elements", []):
        txt = el.get("content", {}).get("text")
        if txt:
            text_chunks.append(txt)

    page_text[pno] = "\n".join(text_chunks)

# --- Inject text into sections ---
for section in sections:
    start = section.get("page_start")
    end = section.get("page_end")

    collected = []
    for p in range(start, end + 1):
        if p in page_text:
            collected.append(page_text[p])

    section["text"] = "\n\n".join(collected).strip()

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("Section text injected correctly into document_structure.sections")
