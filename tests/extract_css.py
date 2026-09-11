import os

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ui_path = os.path.join(root, "executable", "ui.html")
target_css = os.path.join(root, "executable_test", "src", "index.css")

with open(ui_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find <style> and </style>
start_idx = content.find("<style>") + len("<style>")
end_idx = content.find("</style>")

css = content[start_idx:end_idx].strip()

full_content = '@import "tailwindcss";\n\n' + css + '\n'

with open(target_css, "w", encoding="utf-8") as f:
    f.write(full_content)

print(f"Extracted {len(css)} bytes of CSS from {ui_path} to {target_css}")
