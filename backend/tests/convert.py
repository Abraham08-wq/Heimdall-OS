import markdown2
from weasyprint import HTML

with open('system_analysis.md', 'r') as f:
    text = f.read()

html = markdown2.markdown(text)
html_full = f"""
<!DOCTYPE html>
<html>
<head>
<style>
body {{ font-family: Arial, sans-serif; line-height: 1.6; padding: 2em; }}
h1 {{ color: #2c3e50; }}
h2 {{ color: #34495e; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }}
h3 {{ color: #7f8c8d; }}
code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; font-family: monospace; }}
</style>
</head>
<body>
{html}
</body>
</html>
"""

HTML(string=html_full).write_pdf('system_analysis.pdf')
