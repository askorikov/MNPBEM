#!/usr/bin/env python3
"""Build a standalone, browsable HTML help site for the MNPBEM toolbox.

Reads the MATLAB `publish` output in ./html (one page per .m file) plus the
table of contents in ./helptoc.xml, and rewrites every page into a self
contained shell that adds:

  * a persistent, collapsible sidebar mirroring the TOC tree,
  * a full text search box,
  * prev / next navigation derived from the TOC order,
  * a working "Open in MATLAB" affordance for matlab: links.

Nothing about the original MATLAB workflow is changed; this only assembles
the already-generated HTML into something you can inspect in a plain browser
without MATLAB installed.

Usage:  python3 make_help_site.py
Output: ./site/  (open site/index.html)
"""

import html
import json
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from urllib.parse import quote


HELP_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_DIR = os.path.join(HELP_DIR, "html")
TOC_XML = os.path.join(HELP_DIR, "helptoc.xml")
OUT_DIR = os.path.join(HELP_DIR, "site")


# --------------------------------------------------------------------------- #
# Table of contents
# --------------------------------------------------------------------------- #
def load_toc():
    """Parse helptoc.xml into a flat (in reading order) list of nodes.

    Each node: {"title": str, "target": "foo.html" or None, "level": int,
                "children": [nodes]}
    """
    tree = ET.parse(TOC_XML)
    root = tree.getroot()

    def walk(node, level):
        # Only the item's own direct text is its label; itertext() would
        # swallow every descendant's text and collapse the whole tree.
        title = (node.text or "").strip()
        target = node.get("target")
        if target:
            target = os.path.basename(target)
        children = [walk(c, level + 1) for c in node.findall("tocitem")]
        return {"title": title, "target": target, "level": level,
                "children": children}

    top = [walk(c, 0) for c in root.findall("tocitem")]

    # Flatten in reading order, skipping container-only nodes (no target).
    flat = []
    def flatten(nodes):
        for n in nodes:
            if n["target"]:
                flat.append(n)
            flatten(n["children"])
    flatten(top)

    # De-duplicate by target, keeping first occurrence.
    seen = set()
    uniq = []
    for n in flat:
        if n["target"] not in seen:
            seen.add(n["target"])
            uniq.append(n)
    return top, uniq


# --------------------------------------------------------------------------- #
# Content extraction
# --------------------------------------------------------------------------- #
CONTENT_START = '<div class="content">'

def extract_content(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    start = text.find(CONTENT_START)
    if start == -1:
        # Fallback: use whatever is inside <body>.
        b = text.find("<body>")
        e = text.rfind("</body>")
        content = text[b + len("<body>"):e if e != -1 else len(text)]
    else:
        content = text[start + len(CONTENT_START):]
    # Cut at the first footer (MATLAB renders it as <p> or <div class="footer">)
    # or at the trailing source-comment block, whichever comes first.
    m = re.search(r'<(?:p|div) class="footer">', content)
    if m:
        content = content[:m.start()]
    s = content.find("##### SOURCE BEGIN #####")
    if s != -1:
        content = content[:s]
    content = content.strip()
    title_m = re.search(r"<h1>(.*?)</h1>", content, flags=re.S)
    title = html.unescape(title_m.group(1).strip()) if title_m else os.path.basename(path)
    return content, title


# --------------------------------------------------------------------------- #
# Sidebar + shell
# --------------------------------------------------------------------------- #
def render_sidebar_tree(nodes, active_target):
    """Render nested <ul> sidebar HTML.

    A node with children is rendered as a single collapsible branch; a
    leaf is a single link.  Nodes that are both (most TOC items have a
    target AND sub-items) get rendered as a branch whose label is also
    a link, so the entry is never duplicated.
    """
    def render(items):
        parts = ['<ul>']
        for n in items:
            is_active = n["target"] == active_target
            label = html.escape(n["title"])
            if n["children"]:
                branch_cls = "branch active" if is_active else "branch"
                href = n["target"] if n["target"] else "javascript:void(0)"
                parts.append(f'<li class="{branch_cls}">')
                parts.append(f'<a class="branch-toggle" href="{href}">{label}</a>')
                parts.append(render(n["children"]))
                parts.append('</li>')
            else:
                cls = "leaf active" if is_active else "leaf"
                parts.append(
                    f'<li class="{cls}"><a href="{n["target"]}">{label}</a></li>'
                )
        parts.append('</ul>')
        return "".join(parts)
    return render(nodes)


def prev_next(flat, target):
    for i, n in enumerate(flat):
        if n["target"] == target:
            prev = flat[i - 1]["target"] if i > 0 else None
            nxt = flat[i + 1]["target"] if i < len(flat) - 1 else None
            return prev, nxt
    return None, None


SHELL_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} - MNPBEM</title>
<style>
:root {{
  --sidebar-w: 320px;
  --accent: #d55000;
  --accent-soft: #fdf0e8;
  --link: #005fce;
  --border: #e3e3e3;
  --bg: #ffffff;
  --sidebar-bg: #fafafa;
  --text: #222;
}}
* {{ box-sizing: border-box; }}
html, body {{ height: 100%; margin: 0; }}
body {{
  font-family: Arial, Helvetica, sans-serif;
  color: var(--text);
  background: var(--bg);
  line-height: 1.5;
}}
a {{ color: var(--link); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

/* layout */
#layout {{ display: flex; height: 100vh; }}
#sidebar {{
  width: var(--sidebar-w);
  min-width: var(--sidebar-w);
  min-height: 0;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  padding: 14px 10px 40px;
  transition: margin-left .2s ease;
}}
#main {{ flex: 1; min-height: 0; overflow-y: auto; }}
#content-wrap {{ max-width: 900px; margin: 0 auto; padding: 28px 40px 80px; }}

/* top bar */
#topbar {{
  position: sticky; top: 0; z-index: 5;
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px;
  background: #fff;
  border-bottom: 1px solid var(--border);
}}
#brand {{ font-weight: bold; color: var(--accent); font-size: 15px; white-space: nowrap; }}
#brand span {{ color: #666; font-weight: normal; }}
#menu-btn {{
  border: 1px solid var(--border); background: #fff; border-radius: 6px;
  padding: 5px 10px; cursor: pointer; font-size: 14px;
}}
#search {{
  flex: 1; max-width: 420px;
  padding: 6px 10px; border: 1px solid var(--border); border-radius: 6px;
  font-size: 13px;
}}
#search-count {{ font-size: 12px; color: #777; white-space: nowrap; }}

/* sidebar tree */
#sidebar h2 {{
  font-size: 13px; text-transform: uppercase; letter-spacing: .04em;
  color: #888; margin: 0 6px 10px;
  position: sticky; top: 0; background: var(--sidebar-bg);
  padding-top: 6px;
}}
#sidebar ul {{ list-style: none; margin: 0; padding: 0; }}
#sidebar li {{ margin: 1px 0; }}
#sidebar .leaf > a, #sidebar .branch > .branch-toggle {{
  display: block; padding: 5px 8px; border-radius: 6px; font-size: 13.5px;
  color: var(--text);
}}
#sidebar .leaf > a:hover {{ background: var(--accent-soft); text-decoration: none; }}
#sidebar .leaf.active > a {{ background: var(--accent); color: #fff; font-weight: bold; }}
#sidebar .branch.active > .branch-toggle {{ background: var(--accent); color: #fff; }}
#sidebar .branch > .branch-toggle {{
  font-weight: 600; color: #333; cursor: pointer;
  display: flex; align-items: center; gap: 6px;
}}
#sidebar .branch > .branch-toggle::before {{
  content: "\\25B8"; display: inline-block; width: 12px; transition: transform .15s;
  color: #999; font-size: 11px;
}}
#sidebar .branch.open > .branch-toggle::before {{ transform: rotate(90deg); }}
#sidebar .branch > ul {{ display: none; margin-left: 14px; border-left: 1px solid var(--border); padding-left: 4px; }}
#sidebar .branch.open > ul {{ display: block; }}

/* content: reuse the MATLAB publish typography */
.content h1 {{ padding:0; margin:0 0 22px; font-family:Arial, Helvetica, sans-serif; font-size:1.6em; color:var(--accent); line-height:100%; font-weight:normal; }}
h2 {{ padding:0; margin:0 0 8px; font-family:Arial, Helvetica, sans-serif; font-size:1.2em; color:#000; font-weight:bold; line-height:140%; border-bottom:1px solid #d6d4d4; display:block; margin-top:26px; }}
h3 {{ padding:0; margin:0 0 5px; font-family:Arial, Helvetica, sans-serif; font-size:1.1em; color:#000; font-weight:bold; line-height:140%; }}
p {{ margin:0 0 18px; }}
ul {{ margin:0 0 18px 23px; list-style:square; }}
ol {{ margin:0 0 18px 0; list-style:decimal; }}
li {{ margin:0 0 6px 0; }}
ul li ul {{ margin:0 0 7px 23px; }}
tt, code {{ font-family: Consolas, Menlo, monospace; font-size: .95em; background:#f4f4f4; padding:1px 4px; border-radius:3px; }}
pre, code {{ font-size:12px; }}
pre {{ margin:0 0 18px; }}
pre.codeinput {{ padding:10px; border:1px solid #d3d3d3; background:#f7f7f7; overflow-x:auto; line-height:1.45; }}
pre.codeoutput {{ padding:10px 11px; margin:0 0 18px; color:#4c4c4c; }}
pre.error {{ color:red; }}
img {{ max-width:100%; margin:4px 0 18px; }}
table th {{ padding:7px 5px; text-align:left; vertical-align:middle; border:1px solid #d6d4d4; font-weight:bold; }}
table td {{ padding:7px 5px; text-align:left; vertical-align:top; border:1px solid #d6d4d4; }}
span.keyword {{ color:#0000FF; }}
span.comment {{ color:#228B22; }}
span.string {{ color:#A020F0; }}
span.untermstring {{ color:#B20000; }}
span.syscmd {{ color:#B28C00; }}
span.typesection {{ color:#A0522D; }}

/* matlab: links (no-op in browser) */
a.matlab-link {{ color:#8a8a8a; border-bottom:1px dotted #bbb; cursor:default; }}
a.matlab-link::after {{ content:" (MATLAB)"; font-size:.8em; color:#bbb; }}

/* nav footer */
#page-nav {{
  display:flex; justify-content:space-between; gap:12px;
  margin-top:48px; padding-top:18px; border-top:1px solid var(--border);
}}
#page-nav a {{ padding:8px 14px; border:1px solid var(--border); border-radius:8px; background:#fafafa; }}
#page-nav a:hover {{ background:var(--accent-soft); text-decoration:none; }}
#page-nav .nav-label {{ display:block; font-size:11px; color:#999; text-transform:uppercase; letter-spacing:.03em; }}

/* search highlight */
mark {{ background:#ffe58a; color:inherit; padding:0 1px; border-radius:2px; }}

/* responsive */
@media (max-width: 780px) {{
  #layout {{ flex-direction: column; }}
  #sidebar {{ width:100%; min-width:0; max-height:50vh; border-right:none; border-bottom:1px solid var(--border); }}
  #content-wrap {{ padding:20px; }}
}}
</style>
</head>
<body>
<div id="layout">
  <nav id="sidebar">
    <h2>{toc_root_title}</h2>
    {sidebar_html}
  </nav>
  <div id="main">
    <div id="topbar">
      <button id="menu-btn" title="Toggle navigation">&#9776;</button>
      <div id="brand">MNPBEM <span>Help</span></div>
      <input id="search" type="search" placeholder="Search this page..." autocomplete="off">
      <span id="search-count"></span>
    </div>
    <div id="content-wrap">
      <div class="content">
{content}
      </div>
      <div id="page-nav">
        <div>{prev_link}</div>
        <div style="text-align:right">{next_link}</div>
      </div>
    </div>
  </div>
</div>

<script>
(function () {{
  // Expand every branch that contains the active page; leave others open too for simplicity.
  var active = document.querySelector('#sidebar .leaf.active');
  document.querySelectorAll('#sidebar .branch').forEach(function (b) {{ b.classList.add('open'); }});

  // Sidebar toggle (mobile / narrow screens).
  var menuBtn = document.getElementById('menu-btn');
  var sidebar = document.getElementById('sidebar');
  menuBtn.addEventListener('click', function () {{
    sidebar.style.display = (sidebar.style.display === 'none') ? '' : 'none';
  }});

  // Branch collapse toggles: clicking always expands/collapses, and if
  // the label is a real link it also navigates.
  document.querySelectorAll('#sidebar .branch-toggle').forEach(function (t) {{
    t.addEventListener('click', function (e) {{
      t.parentElement.classList.toggle('open');
      if (t.getAttribute('href') === 'javascript:void(0)') {{
        e.preventDefault();
      }}
    }});
  }});

  // matlab: links -> make inert, but keep them discoverable.
  document.querySelectorAll('a[href^="matlab:"]').forEach(function (a) {{
    a.classList.add('matlab-link');
    a.setAttribute('data-matlab', a.getAttribute('href'));
    a.setAttribute('href', 'javascript:void(0)');
    a.title = 'Requires MATLAB: ' + a.getAttribute('data-matlab');
  }});

  // Per-page search with highlighting.
  var search = document.getElementById('search');
  var countEl = document.getElementById('search-count');
  var content = document.querySelector('.content');
  function clearMarks() {{
    content.querySelectorAll('mark').forEach(function (m) {{
      var p = m.parentNode; p.replaceChild(document.createTextNode(m.textContent), m); p.normalize();
    }});
  }}
  function highlightText(node, q) {{
    var text = node.nodeValue, lower = text.toLowerCase(), ql = q.toLowerCase();
    var out = document.createDocumentFragment(), pos = 0, idx, total = 0;
    while ((idx = lower.indexOf(ql, pos)) !== -1) {{
      total += 1;
      out.appendChild(document.createTextNode(text.slice(pos, idx)));
      var mark = document.createElement('mark');
      mark.textContent = text.slice(idx, idx + q.length);
      out.appendChild(mark);
      pos = idx + q.length;
    }}
    out.appendChild(document.createTextNode(text.slice(pos)));
    node.parentNode.replaceChild(out, node);
    return total;
  }}
  function doSearch(q) {{
    clearMarks();
    if (!q) {{ countEl.textContent = ''; return; }}
    var walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT, {{
      acceptNode: function (n) {{
        if (!n.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
        var tag = n.parentElement && n.parentElement.tagName;
        if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'MARK') return NodeFilter.FILTER_REJECT;
        return n.nodeValue.toLowerCase().indexOf(q.toLowerCase()) !== -1
          ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }}
    }});
    var nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
    var total = 0;
    nodes.forEach(function (n) {{ total += highlightText(n, q); }});
    countEl.textContent = total ? total + ' match' + (total > 1 ? 'es' : '') : 'no matches';
    var first = content.querySelector('mark');
    if (first) first.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
  }}
  var debounce;
  search.addEventListener('input', function () {{
    clearTimeout(debounce);
    var q = search.value.trim();
    debounce = setTimeout(function () {{ doSearch(q); }}, 150);
  }});
  search.addEventListener('keydown', function (e) {{ if (e.key === 'Escape') {{ search.value=''; doSearch(''); }} }});
}})();
</script>
</body>
</html>
"""


def main():
    top, flat = load_toc()
    root_title = top[0]["title"] if top else "MNPBEM"

    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    site_html = os.path.join(OUT_DIR, "html")
    os.makedirs(site_html)

    # Collect the set of published pages that exist on disk.
    available = {f for f in os.listdir(HTML_DIR) if f.endswith(".html")}

    written = 0
    order_index = {n["target"]: i for i, n in enumerate(flat)}

    link_fixes = {
        "bem_u_comparticle.html": "bem_ug_comparticle.html",
        "ug_bem_layergreen.html": "bem_ug_layergreen.html",
        "./mnpbem_ug_symmetry.html": "bem_ug_symmetry.html",
        "bem_ug_ploygon3d.html": "bem_ug_polygon3.html",
    }

    for n in flat:
        target = n["target"]
        if target not in available:
            print("  ! skipping (no html):", target)
            continue
        src = os.path.join(HTML_DIR, target)
        content, title = extract_content(src)
        for bad, good in link_fixes.items():
            content = content.replace(f'href="{bad}"', f'href="{good}"')
        prev, nxt = prev_next(flat, target)

        prev_link = (f'<a href="{prev}"><span class="nav-label">Previous</span>'
                     f'{html.escape(next_title(flat, order_index, prev))}</a>') if prev else ''
        next_link = (f'<a href="{nxt}"><span class="nav-label">Next</span>'
                     f'{html.escape(next_title(flat, order_index, nxt))}</a>') if nxt else ''

        page = SHELL_TEMPLATE.format(
            title=html.escape(title),
            toc_root_title=html.escape(root_title),
            sidebar_html=render_sidebar_tree(top, target),
            content=content,
            prev_link=prev_link,
            next_link=next_link,
        )
        # Pages live under site/html/ so "../figures/..." refs resolve.
        out_path = os.path.join(site_html, target)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(page)
        written += 1

    # Copy figures and any inline images so relative srcs resolve.
    fig_src = os.path.join(HELP_DIR, "figures")
    if os.path.isdir(fig_src):
        fig_dst = os.path.join(OUT_DIR, "figures")
        shutil.copytree(fig_src, fig_dst)

    for f in os.listdir(HTML_DIR):
        if not f.endswith(".html"):
            shutil.copy2(os.path.join(HTML_DIR, f), os.path.join(site_html, f))

    # index.html -> first content page (the product page) as landing.
    landing = ("bem_product_page.html" if "bem_product_page.html" in available
               else os.path.basename(flat[0]["target"]))
    landing_url = "html/" + landing
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(f'<!DOCTYPE html><html><head><meta http-equiv="refresh" '
                f'content="0; url={landing_url}"></head><body>'
                f'Redirecting to <a href="{landing_url}">{landing}</a>...</body></html>')

    print(f"Wrote {written} pages to {os.path.relpath(OUT_DIR, HELP_DIR)}/")
    print(f"Open {os.path.relpath(os.path.join(OUT_DIR, 'index.html'), HELP_DIR)} in a browser.")


def next_title(flat, order_index, target):
    i = order_index.get(target)
    if i is None:
        return ""
    return flat[i]["title"]


if __name__ == "__main__":
    main()
