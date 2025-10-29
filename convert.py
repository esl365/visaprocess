import re
import html
from pathlib import Path

def main() -> None:
    md_path = Path('ViDocPrep.md')
    lines = md_path.read_text(encoding='utf-8').splitlines()

    html_lines: list[str] = []
    list_stack: list[dict[str, int]] = []
    blockquote_level = 0
    paragraph_lines: list[str] = []
    heading_ids: list[str] = []

    def process_inline(text: str) -> str:
        text = html.escape(text)
        text = re.sub(r'\[(.+?)\]\((.+?)\)', lambda m: f'<a href="{html.escape(m.group(2), quote=True)}" target="_blank">{m.group(1)}</a>', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
        text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        replacements = {
            '☐': '&#9744;',
            '☑': '&#9745;',
            '✅': '&#9989;',
            '🔴': '&#128308;',
            '⏰': '&#9203;'
        }
        for key, value in replacements.items():
            text = text.replace(key, value)
        return text

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if paragraph_lines:
            joined = ' '.join(paragraph_lines).strip()
            if joined:
                html_lines.append(f'<p>{process_inline(joined)}</p>')
            paragraph_lines = []

    def close_lists_to(indent: int) -> None:
        nonlocal list_stack
        while list_stack and indent < list_stack[-1]['indent']:
            closing = list_stack.pop()
            html_lines.append(f"</{closing['tag']}>")

    def close_all_lists() -> None:
        nonlocal list_stack
        while list_stack:
            closing = list_stack.pop()
            html_lines.append(f"</{closing['tag']}>")

    def ensure_list(list_type: str, indent: int) -> None:
        nonlocal list_stack
        close_lists_to(indent)
        if list_stack and list_stack[-1]['indent'] == indent and list_stack[-1]['type'] != list_type:
            closing = list_stack.pop()
            html_lines.append(f"</{closing['tag']}>")
        if not list_stack or indent > list_stack[-1]['indent']:
            tag = 'ol' if list_type == 'ol' else 'ul'
            html_lines.append(f'<{tag} class="list-level">')
            list_stack.append({'type': list_type, 'indent': indent, 'tag': tag})
        elif list_stack[-1]['type'] == list_type and list_stack[-1]['indent'] == indent:
            return

    index = 0
    total_lines = len(lines)

    while index < total_lines:
        raw_line = lines[index]
        working_line = raw_line

        # Determine blockquote depth
        current_depth = 0
        while working_line.lstrip().startswith('>'):
            gt_index = working_line.find('>')
            current_depth += 1
            working_line = working_line[gt_index + 1:]
            if working_line.startswith(' '):
                working_line = working_line[1:]

        if current_depth != blockquote_level:
            flush_paragraph()
            close_all_lists()
            while blockquote_level > current_depth:
                html_lines.append('</blockquote>')
                blockquote_level -= 1
            while blockquote_level < current_depth:
                html_lines.append('<blockquote>')
                blockquote_level += 1

        stripped = working_line.strip()

        # Table handling
        if '|' in stripped and not stripped.startswith('| ---'):
            if index + 1 < total_lines:
                next_line = lines[index + 1]
                separator_pattern = re.compile(r'^\s*\|?(\s*:?-+:?\s*\|)+\s*$')
                if separator_pattern.match(next_line):
                    header_line = working_line
                    table_rows: list[str] = []
                    index += 2
                    while index < total_lines and '|' in lines[index]:
                        table_rows.append(lines[index].strip())
                        index += 1
                    header_cells = [cell.strip() for cell in header_line.strip().strip('|').split('|')]
                    html_lines.append('<table>')
                    html_lines.append('<thead><tr>' + ''.join(f'<th>{process_inline(cell)}</th>' for cell in header_cells) + '</tr></thead>')
                    html_lines.append('<tbody>')
                    for row in table_rows:
                        cells = [cell.strip() for cell in row.strip().strip('|').split('|')]
                        html_lines.append('<tr>' + ''.join(f'<td>{process_inline(cell)}</td>' for cell in cells) + '</tr>')
                    html_lines.append('</tbody></table>')
                    continue

        compact = stripped.replace(' ', '')
        if compact and all(ch == compact[0] for ch in compact) and compact[0] in '-*_' and len(compact) >= 3:
            flush_paragraph()
            close_all_lists()
            html_lines.append('<hr>')
            index += 1
            continue

        heading_match = re.match(r'^(#{1,6})\s+(.+)', working_line)
        if heading_match:
            flush_paragraph()
            close_all_lists()
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            anchor = re.sub(r'[^a-z0-9]+', '-', heading_text.lower()).strip('-')
            original = anchor
            suffix = 2
            while anchor in heading_ids:
                anchor = f'{original}-{suffix}'
                suffix += 1
            heading_ids.append(anchor)
            html_lines.append(f'<h{level} id="{anchor}">{process_inline(heading_text)}</h{level}>')
            index += 1
            continue

        bullet_match = re.match(r'^(\s*)([-+*])\s+(.*)', working_line)
        if bullet_match:
            indent = len(bullet_match.group(1).replace('\t', '    '))
            item_content = bullet_match.group(3).strip()
            checkbox_match = re.match(r'\[( |x|X)\]\s*(.*)', item_content)
            checkbox_html = ''
            if checkbox_match:
                checked = checkbox_match.group(1).lower() == 'x'
                item_content = checkbox_match.group(2)
                checkbox_html = f'<span class="checkbox {"checked" if checked else ""}">{"&#9745;" if checked else "&#9744;"}</span>'
            flush_paragraph()
            ensure_list('ul', indent)
            html_lines.append(f'<li>{checkbox_html}{process_inline(item_content)}</li>')
            index += 1
            continue

        ordered_match = re.match(r'^(\s*)(\d+)\.\s+(.*)', working_line)
        if ordered_match:
            indent = len(ordered_match.group(1).replace('\t', '    '))
            item_content = ordered_match.group(3).strip()
            flush_paragraph()
            ensure_list('ol', indent)
            html_lines.append(f'<li>{process_inline(item_content)}</li>')
            index += 1
            continue

        if stripped == '':
            flush_paragraph()
            index += 1
            continue

        paragraph_lines.append(working_line)
        index += 1

    flush_paragraph()
    close_all_lists()
    while blockquote_level:
        html_lines.append('</blockquote>')
        blockquote_level -= 1

    body_html = '\n'.join(html_lines)

    headings = re.findall(r'<h([1-6]) id="([^"]+)">(.+?)</h\1>', body_html)
    nav_items: list[tuple[int, str, str]] = []
    for level, anchor, text in headings:
        nav_items.append((int(level), anchor, text))

    class TocNode:
        __slots__ = ('level', 'anchor', 'text', 'children')

        def __init__(self, level: int, anchor: str, text: str) -> None:
            self.level = level
            self.anchor = anchor
            self.text = text
            self.children: list['TocNode'] = []

    root = TocNode(0, '', '')
    stack: list[TocNode] = [root]
    for level, anchor, text in nav_items:
        level = max(level, 1)
        while stack and stack[-1].level >= level:
            stack.pop()
        node = TocNode(level, anchor, text)
        stack[-1].children.append(node)
        stack.append(node)

    def render_nodes(nodes: list[TocNode], depth: int = 0) -> list[str]:
        if not nodes:
            return []
        indent = '  ' * (depth + 1)
        parts = [f"{indent}<ul>"]
        for node in nodes:
            item_indent = '  ' * (depth + 2)
            parts.append(f"{item_indent}<li><a href='#%s'>%s</a>" % (node.anchor, node.text))
            parts.extend(render_nodes(node.children, depth + 2))
            parts.append(f"{item_indent}</li>")
        parts.append(f"{indent}</ul>")
        return parts

    nav_parts = ["<nav class='toc'>", "  <h2>Table of Contents</h2>"]
    nav_parts.extend(render_nodes(root.children))
    nav_parts.append("</nav>")
    nav_html = '\n'.join(nav_parts)

    style = """
:root {
  color-scheme: light;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif;
}
body {
  margin: 0;
  padding: 0;
  background-color: #f7f4f1;
  color: #2b2118;
}
main {
  max-width: 960px;
  margin: 0 auto;
  padding: 3rem 1.5rem 5rem;
  line-height: 1.65;
}
header {
  background: linear-gradient(135deg, #45260a, #8d5524);
  color: #fff;
  padding: 3rem 1.5rem;
  text-align: center;
  box-shadow: 0 8px 20px rgba(69, 38, 10, 0.25);
}
header h1 {
  font-size: 2.4rem;
  margin-bottom: 0.75rem;
}
header p {
  font-size: 1.1rem;
  max-width: 720px;
  margin: 0.5rem auto 0;
}
.toc {
  background: #fff;
  border-radius: 16px;
  padding: 1.75rem;
  box-shadow: 0 12px 24px rgba(0,0,0,0.08);
  margin: -4rem auto 3rem;
  max-width: 860px;
  border: 1px solid rgba(69,38,10,0.08);
}
.toc ul {
  list-style: none;
  padding-left: 1rem;
  margin: 0;
}
.toc li {
  margin: 0.35rem 0;
}
.toc a {
  color: #8d5524;
  text-decoration: none;
}
.toc a:hover,
.toc a:focus {
  text-decoration: underline;
}
h1, h2, h3, h4, h5, h6 {
  color: #42210b;
  margin-top: 2.4rem;
  margin-bottom: 1rem;
  line-height: 1.25;
}
p {
  margin: 1rem 0;
  font-size: 1.02rem;
}
ul, ol {
  margin: 0.75rem 0 0.75rem 1.5rem;
}
li {
  margin: 0.4rem 0;
}
blockquote {
  border-left: 4px solid #ae6031;
  padding-left: 1rem;
  margin-left: 0;
  background: rgba(174, 96, 49, 0.08);
  border-radius: 0 12px 12px 0;
}
hr {
  border: none;
  border-top: 2px solid rgba(69,38,10,0.12);
  margin: 3rem 0;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1.5rem 0;
  background: #fff;
  overflow: hidden;
  border-radius: 14px;
  box-shadow: 0 8px 20px rgba(0,0,0,0.05);
}
th, td {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid rgba(69,38,10,0.08);
  text-align: left;
}
th {
  background: rgba(174, 96, 49, 0.12);
  font-weight: 700;
}
tr:last-child td {
  border-bottom: none;
}
a {
  color: #8d5524;
}
.checkbox {
  display: inline-flex;
  width: 1.25rem;
  height: 1.25rem;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  border: 2px solid rgba(69,38,10,0.4);
  margin-right: 0.5rem;
  font-size: 0.9rem;
}
.checkbox.checked {
  background: #ae6031;
  color: #fff;
  border-color: #ae6031;
}
code {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  background: rgba(174, 96, 49, 0.15);
  padding: 0.15rem 0.3rem;
  border-radius: 6px;
}
@media (max-width: 768px) {
  main {
    padding: 2rem 1rem 3rem;
  }
  header {
    padding: 2.5rem 1rem;
  }
  .toc {
    margin-top: -3.5rem;
    padding: 1.25rem;
  }
  table {
    font-size: 0.95rem;
    overflow-x: auto;
    display: block;
  }
}
"""

    html_doc = f"""<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Kang & Kriel Recruitment – E-2 Visa Document Prep Guide</title>
<meta name='description' content='Complete E-2 visa timeline and document preparation guide for U.S. citizens heading to Korea.'>
<style>{style}</style>
</head>
<body>
<header>
  <h1>Kang &amp; Kriel Recruitment – E-2 Visa Document Prep Guide</h1>
  <p>Complete step-by-step guide for preparing, authenticating, and shipping documents for the Korean E-2 visa. Includes fast-track checklists, professional service recommendations, and arrival tasks.</p>
</header>
{nav_html}
<main>
{body_html}
</main>
<footer style='text-align:center;padding:2rem 1rem;color:rgba(66,33,11,0.75);'>
  <p>Updated from ViDocPrep.md • Optimized for offline sharing</p>
</footer>
</body>
</html>"""

    Path('e2-visa-timeline-optimized.html').write_text(html_doc, encoding='utf-8')

if __name__ == '__main__':
    main()
