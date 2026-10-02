"""Render technical_report.md to KHLab_Report.pdf (A4) with the SVG figures inlined.

Needs Playwright with Chromium; only the report build uses it, never `make run`.

    python3 src/report/build_pdf.py
"""
import html, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MD = ROOT / "technical_report.md"
PDF = ROOT / "KHLab_Report.pdf"

CSS = """
@page { size: A4; margin: 15mm 16mm 15mm 16mm; }
body { font: 9.4pt/1.42 'Helvetica Neue', Arial, sans-serif; color: #1d1d1f; }
h1 { font-size: 16pt; line-height: 1.2; margin: 0 0 6pt; }
h2 { font-size: 12pt; margin: 12pt 0 4pt; border-bottom: 1px solid #d2d2d7; padding-bottom: 2pt; }
h3 { font-size: 10pt; margin: 8pt 0 3pt; }
p, li { margin: 0 0 5pt; }
ul { padding-left: 14pt; margin: 0 0 5pt; }
blockquote { margin: 0 0 8pt; padding: 6pt 10pt; background: #f5f5f7; border-left: 3px solid #c8102e; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 8pt; font-size: 8.6pt; }
th, td { border-bottom: 1px solid #e5e5ea; padding: 3pt 4pt; text-align: left; vertical-align: top; }
th { background: #f5f5f7; }
code { font: 8.4pt Menlo, monospace; background: #f5f5f7; padding: 0 2px; border-radius: 2px; }
hr { border: 0; border-top: 1px solid #d2d2d7; margin: 6pt 0; }
figure { margin: 2pt 0 8pt; text-align: center; break-inside: avoid; }
figure svg { width: 82%; height: auto; }
"""


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<a href='\2'>\1</a>", s)
    return s


def convert(md):
    out, para, lines = [], [], md.splitlines()
    i = 0

    def flush():
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()
    while i < len(lines):
        ln = lines[i]
        img = re.match(r"!\[([^\]]*)\]\(([^)]+\.svg)\)", ln.strip())
        if img:
            flush()
            out.append(f"<figure>{(ROOT / img.group(2)).read_text()}</figure>")
        elif ln.startswith("#"):
            flush()
            n = len(ln) - len(ln.lstrip("#"))
            out.append(f"<h{n}>{inline(ln[n:].strip())}</h{n}>")
        elif ln.strip() == "----" or ln.strip() == "---":
            flush()
            out.append("<hr>")
        elif ln.startswith(">"):
            flush()
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(lines[i][1:].strip())
                i += 1
            out.append(f"<blockquote>{inline(' '.join(block))}</blockquote>")
            continue
        elif ln.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head, body = rows[0], [r for r in rows[2:]]
            t = "<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr>"
            t += "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
            out.append(t + "</table>")
            continue
        elif re.match(r"^(\s*[-*] |\d+\. )", ln):
            flush()
            tag = "ol" if re.match(r"^\d+\. ", ln) else "ul"
            items = []
            while i < len(lines) and lines[i].strip():
                cur = lines[i]
                if re.match(r"^(\s*[-*] |\d+\. )", cur):
                    items.append(re.sub(r"^(\s*[-*] |\d+\. )", "", cur))
                else:
                    items[-1] += " " + cur.strip()
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        elif not ln.strip():
            flush()
        else:
            para.append(ln.strip())
        i += 1
    flush()
    return "\n".join(out)


def main():
    from playwright.sync_api import sync_playwright
    body = convert(MD.read_text())
    doc = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
    (ROOT / "docs" / "report.html").write_text(doc)
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.set_content(doc, wait_until="load")
        page.pdf(path=str(PDF), format="A4", print_background=True, prefer_css_page_size=True)
        b.close()
    pages = len(re.findall(rb"/Type\s*/Page[^s]", PDF.read_bytes()))
    print(f"wrote {PDF.name}: {pages} page(s)")
    if pages > 6:
        sys.exit("over the 6-page limit")


if __name__ == "__main__":
    main()
