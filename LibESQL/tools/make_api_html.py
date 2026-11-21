#!/usr/bin/env python3
"""
make_api_html.py - build "API Reference.html" from "API Reference.md".

    python tools/make_api_html.py            (run from the LibESQL folder, or anywhere)

The page is one self-contained file: contents sidebar, search that filters the
reference as you type, copy buttons on code, SQL/Lua colouring, light and dark
themes. Anchors match GitHub's, so links inside the reference keep working.
Needs Python 3.7+ and nothing else. MIT licensed, part of LibESQL.
"""

import html
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)
SRC = os.path.join(LIB, "API Reference.md")
OUT = os.path.join(LIB, "API Reference.html")

# --------------------------------------------------------------------------
# Inline markdown
# --------------------------------------------------------------------------

def slugify(text, used):
    s = re.sub(r"[^\w\- ]", "", text.lower()).replace(" ", "-")
    slug, n = s, 0
    while slug in used:
        n += 1
        slug = "%s-%d" % (s, n)
    used.add(slug)
    return slug


def link_target(url):
    if url.startswith("#") or re.match(r"^[a-z]+://", url):
        return url
    # relative links point at files next to the reference
    return url


def inline(text):
    codes = []

    def keep_code(m):
        codes.append(m.group(1))
        return "\x00%d\x00" % (len(codes) - 1)

    text = re.sub(r"`([^`]+)`", keep_code, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)

    def link(m):
        return '<a href="%s">%s</a>' % (html.escape(link_target(m.group(2))), m.group(1))

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    text = text.replace("\\|", "|")

    def put_code(m):
        return "<code>%s</code>" % html.escape(codes[int(m.group(1))].replace("\\|", "|"), quote=False)

    return re.sub(r"\x00(\d+)\x00", put_code, text)

# --------------------------------------------------------------------------
# Code colouring (small and safe: unknown text is left plain)
# --------------------------------------------------------------------------

SQL_WORDS = set("""SELECT DISTINCT FROM WHERE GROUP BY HAVING ORDER ASC DESC LIMIT OFFSET AND OR NOT LIKE IN BETWEEN
IS NULL TRUE FALSE AS JOIN INNER LEFT OUTER CROSS ON INTO CASE WHEN THEN ELSE END CAST EXISTS ALL INSERT UPDATE
DELETE CREATE TABLE VALUES SET SHOW TABLES DESCRIBE DROP REFRESH SCAN HELP IF UPSERT REPLACE IGNORE CONFLICT DO
NOTHING DUPLICATE KEY PRIMARY EXCLUDED ESCAPE INT INTEGER REAL TEXT BOOL""".split())
LUA_WORDS = set("""local function end if then else elseif for in do return nil true false and or not while
repeat until break""".split())


def colour(code, lang):
    out = []
    i, n = 0, len(code)
    words = SQL_WORDS if lang == "sql" else LUA_WORDS

    def span(cls, s):
        out.append('<span class="%s">%s</span>' % (cls, html.escape(s, quote=False)))

    while i < n:
        c = code[i]
        if code.startswith("--", i):
            if lang == "lua" and code.startswith("--[[", i):
                j = code.find("]]", i)
                j = n if j < 0 else j + 2
            else:
                j = code.find("\n", i)
                j = n if j < 0 else j
            span("c", code[i:j]); i = j
        elif lang == "lua" and code.startswith("[[", i):
            j = code.find("]]", i)
            j = n if j < 0 else j + 2
            span("s", code[i:j]); i = j
        elif c in "'\"" and (lang == "lua" or c == "'"):
            j = i + 1
            while j < n:
                if code[j] == "\\" and lang == "lua":
                    j += 2
                    continue
                if code[j] == c:
                    if lang == "sql" and j + 1 < n and code[j + 1] == c:
                        j += 2
                        continue
                    break
                if code[j] == "\n":
                    break
                j += 1
            j = min(j + 1, n)
            span("s", code[i:j]); i = j
        elif c.isdigit():
            m = re.match(r"0[xX][0-9A-Fa-f]+|\d+(\.\d+)?([eE][+-]?\d+)?", code[i:])
            span("n", m.group()); i += len(m.group())
        elif c.isalpha() or c == "_":
            m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", code[i:])
            w = m.group()
            j = i + len(w)
            if (w.upper() if lang == "sql" else w) in words:
                span("k", w)
            elif code[j:j + 1] == "(" or (lang == "lua" and code[j:j + 1] == "." and w == "LibESQL"):
                span("f", w)
            else:
                out.append(html.escape(w, quote=False))
            i = j
        elif lang == "sql" and c == "?":
            span("p", c); i += 1
        else:
            out.append(html.escape(c, quote=False)); i += 1
    return "".join(out)


def guess_lang(lang, code):
    if lang in ("lua", "sql"):
        return lang
    first = code.strip().split(None, 1)[0].upper() if code.strip() else ""
    if first in ("SELECT", "INSERT", "UPSERT", "REPLACE", "UPDATE", "DELETE", "CREATE", "SHOW", "DESCRIBE",
                 "DROP", "SCAN", "REFRESH", "ITEM", "SOURCE", "WITH"):
        return "sql"
    if re.search(r"\blocal\b|\bfunction\b|LibESQL\.|=\s*{", code):
        return "lua"
    return ""

# --------------------------------------------------------------------------
# Blocks
# --------------------------------------------------------------------------

LIST_RE = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", line)]


def render_list(items):
    """items: [(indent, ordered, text)] -> nested html"""
    out = []
    stack = []   # (indent, tag)
    for indent, ordered, text in items:
        tag = "ol" if ordered else "ul"
        while stack and indent < stack[-1][0]:
            out.append("</li></%s>" % stack.pop()[1])
        if stack and indent == stack[-1][0]:
            out.append("</li>")
        if not stack or indent > stack[-1][0]:
            out.append("<%s>" % tag)
            stack.append((indent, tag))
        out.append("<li>" + inline(text))
    while stack:
        out.append("</li></%s>" % stack.pop()[1])
    return "".join(out)


def convert(md):
    lines = md.split("\n")
    blocks = []      # ("h", level, text, slug) or ("html", text)
    used = set()
    i, n = 0, len(lines)
    para = []

    def flush_para():
        if para:
            blocks.append(("html", "<p>%s</p>" % inline(" ".join(para))))
            para.clear()

    while i < n:
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_para()
            lang = stripped[3:].strip()
            body = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            indent = len(line) - len(line.lstrip())
            code = "\n".join(l[indent:] if l[:indent].strip() == "" else l for l in body)
            lang = guess_lang(lang, code)
            blocks.append(("html", '<div class="code"><button class="copy" type="button">Copy</button>'
                                   '<pre><code class="lang-%s">%s</code></pre></div>' % (lang or "text", colour(code, lang) if lang else html.escape(code, quote=False))))
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_para()
            level, text = len(m.group(1)), m.group(2).strip()
            blocks.append(("h", level, text, slugify(text, used)))
            i += 1
            continue
        if stripped == "---":
            flush_para()
            blocks.append(("html", "<hr>"))
            i += 1
            continue
        if stripped.startswith("|") and i + 1 < n and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            flush_para()
            head = split_row(line)
            rows = []
            i += 2
            while i < n and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            t = ['<div class="table"><table><thead><tr>']
            t += ["<th>%s</th>" % inline(c) for c in head]
            t.append("</tr></thead><tbody>")
            for r in rows:
                t.append("<tr>" + "".join("<td>%s</td>" % inline(c) for c in r) + "</tr>")
            t.append("</tbody></table></div>")
            blocks.append(("html", "".join(t)))
            continue
        if LIST_RE.match(line):
            flush_para()
            items = []
            while i < n:
                lm = LIST_RE.match(lines[i])
                if lm:
                    items.append([len(lm.group(1)), lm.group(2)[0].isdigit(), lm.group(3)])
                    i += 1
                elif lines[i].strip() and items and (lines[i].startswith(" ") and not lines[i].strip().startswith("```")):
                    items[-1][2] += " " + lines[i].strip()       # continuation line
                    i += 1
                elif lines[i].strip() == "" and i + 1 < n and LIST_RE.match(lines[i + 1]) and LIST_RE.match(lines[i + 1]).group(1) != "":
                    i += 1                                          # blank line inside a nested list
                else:
                    break
            blocks.append(("html", render_list(items)))
            continue
        if stripped == "":
            flush_para()
            i += 1
            continue
        para.append(stripped)
        i += 1
    flush_para()
    return blocks

# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------

CSS = r"""
:root{--bg:#f7f8fa;--panel:#fff;--text:#1d2330;--muted:#5d6675;--line:#e2e5ea;--accent:#0b7fb3;--accent-soft:#e3f3fa;
--code-bg:#f2f4f7;--k:#0b6fa4;--f:#8a5a00;--s:#2e7d32;--n:#b4472a;--c:#7a8391;--p:#8e44ad;--mark:#fff1a8;}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0f1318;--panel:#161b22;--text:#e2e6ec;--muted:#9aa4b2;
--line:#2a313b;--accent:#4fc3f7;--accent-soft:#12303d;--code-bg:#1d232c;--k:#4fc3f7;--f:#ffd54f;--s:#a5d6a7;--n:#ffab91;--c:#7f8c8d;--p:#ce93d8;--mark:#5a4b00;}}
:root[data-theme=dark]{--bg:#0f1318;--panel:#161b22;--text:#e2e6ec;--muted:#9aa4b2;--line:#2a313b;--accent:#4fc3f7;
--accent-soft:#12303d;--code-bg:#1d232c;--k:#4fc3f7;--f:#ffd54f;--s:#a5d6a7;--n:#ffab91;--c:#7f8c8d;--p:#ce93d8;--mark:#5a4b00;}
*{box-sizing:border-box}
html{scroll-padding-top:16px}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
code{font:13px/1.5 ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace;background:var(--code-bg);padding:.1em .35em;border-radius:4px}
.layout{display:grid;grid-template-columns:290px minmax(0,1fr);min-height:100vh}
nav{position:sticky;top:0;height:100vh;overflow:auto;border-right:1px solid var(--line);background:var(--panel);padding:16px 14px 40px}
nav h1{font-size:18px;margin:0 0 2px}nav .ver{color:var(--muted);font-size:12.5px;margin-bottom:12px}
.search{position:relative;margin-bottom:6px}
.search input{width:100%;padding:8px 30px 8px 10px;border:1px solid var(--line);border-radius:7px;background:var(--bg);color:var(--text);font:inherit}
.search input:focus{outline:2px solid var(--accent);outline-offset:-1px}
.search kbd{position:absolute;right:8px;top:8px;font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:0 5px}
.count{font-size:12.5px;color:var(--muted);min-height:18px;margin-bottom:8px}
.toc{list-style:none;margin:0;padding:0;font-size:14px}
.toc>li{margin:1px 0}.toc a{display:block;padding:3px 8px;border-radius:5px;color:var(--text)}
.toc a:hover{background:var(--accent-soft);text-decoration:none}.toc a.on{background:var(--accent-soft);color:var(--accent);font-weight:600}
.toc details>summary{list-style:none;cursor:pointer}.toc details>summary::-webkit-details-marker{display:none}
.toc details>summary a{display:inline-block;width:calc(100% - 22px)}
.toc details>summary::before{content:"\25B8";display:inline-block;width:18px;color:var(--muted);transition:transform .15s}
.toc details[open]>summary::before{transform:rotate(90deg)}
.toc ul{list-style:none;margin:0 0 4px 18px;padding:0;font-size:13px}.toc ul a{padding:2px 8px;color:var(--muted)}
.toc .hide{display:none}
.tools{display:flex;gap:6px;margin-top:14px}
.tools button{flex:1;font:inherit;font-size:12.5px;padding:5px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--text);cursor:pointer}
main{padding:28px clamp(16px,4vw,56px) 80px;max-width:1100px}
main h1{font-size:30px;margin:0 0 6px}main h2{font-size:23px;margin:42px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
main h3{font-size:17.5px;margin:28px 0 8px}main h4{font-size:15px}
main h2 a.anchor,main h3 a.anchor{opacity:0;margin-left:6px;font-weight:400}main h2:hover a.anchor,main h3:hover a.anchor{opacity:.7}
hr{border:0;border-top:1px solid var(--line);margin:28px 0}
.table{overflow-x:auto;margin:10px 0 16px;border:1px solid var(--line);border-radius:8px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;vertical-align:top;padding:7px 10px;border-bottom:1px solid var(--line)}
th{background:var(--code-bg);font-weight:600;white-space:nowrap}tr:last-child td{border-bottom:0}
td code{white-space:nowrap}td:last-child code{white-space:normal}
.code{position:relative;margin:10px 0 16px}
pre{margin:0;padding:14px 16px;background:var(--code-bg);border:1px solid var(--line);border-radius:8px;overflow-x:auto}
pre code{background:none;padding:0;font-size:13px}
.copy{position:absolute;top:7px;right:7px;font:12px system-ui,sans-serif;padding:3px 9px;border:1px solid var(--line);border-radius:5px;
background:var(--panel);color:var(--muted);cursor:pointer;opacity:.85}.copy:hover{opacity:1;color:var(--text)}
.k{color:var(--k);font-weight:600}.f{color:var(--f)}.s{color:var(--s)}.n{color:var(--n)}.c{color:var(--c);font-style:italic}.p{color:var(--p);font-weight:600}
mark{background:var(--mark);color:inherit;border-radius:2px;padding:0 1px}
.hidden{display:none!important}
.none{display:none;color:var(--muted);padding:30px 0;font-size:16px}
footer{margin-top:60px;color:var(--muted);font-size:13px}
.menu{display:none}
@media (max-width:900px){.layout{grid-template-columns:1fr}
nav{position:fixed;z-index:5;left:0;top:0;width:86vw;max-width:330px;transform:translateX(-102%);transition:transform .2s;box-shadow:0 0 30px rgba(0,0,0,.25)}
nav.open{transform:none}.menu{display:inline-block;position:sticky;top:8px;z-index:4;margin:8px 0 0 12px;font:inherit;padding:6px 12px;
border:1px solid var(--line);border-radius:7px;background:var(--panel);color:var(--text)}main{padding-top:10px}}
@media print{nav,.menu,.copy{display:none}.layout{display:block}}
"""

JS = r"""
(function(){
  var root=document.documentElement;
  try{var t=localStorage.getItem('libesql-theme');if(t)root.setAttribute('data-theme',t);}catch(e){}
  document.getElementById('theme').addEventListener('click',function(){
    var dark=root.getAttribute('data-theme')==='dark'||(!root.getAttribute('data-theme')&&matchMedia('(prefers-color-scheme: dark)').matches);
    var next=dark?'light':'dark';root.setAttribute('data-theme',next);try{localStorage.setItem('libesql-theme',next);}catch(e){}
  });
  // copy buttons
  document.querySelectorAll('.copy').forEach(function(b){
    b.addEventListener('click',function(){
      var text=b.parentNode.querySelector('code').innerText;
      function done(){b.textContent='Copied';setTimeout(function(){b.textContent='Copy';},1400);}
      if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(text).then(done,fallback);}else{fallback();}
      function fallback(){var ta=document.createElement('textarea');ta.value=text;document.body.appendChild(ta);ta.select();
        try{document.execCommand('copy');done();}catch(e){b.textContent='Select + Ctrl+C';}document.body.removeChild(ta);}
    });
  });
  // search: hide sections that don't contain the words, mark matches
  var input=document.getElementById('q'),count=document.getElementById('count'),none=document.getElementById('none');
  var blocks=[].slice.call(document.querySelectorAll('main .block'));
  var tocLinks={};document.querySelectorAll('.toc a').forEach(function(a){tocLinks[a.getAttribute('href').slice(1)]=a;});
  blocks.forEach(function(b){b._text=b.textContent.toLowerCase();});
  function unmark(){document.querySelectorAll('main mark').forEach(function(m){var p=m.parentNode;p.replaceChild(document.createTextNode(m.textContent),m);p.normalize();});}
  function markIn(el,words){
    var walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT,null),nodes=[],n;
    while((n=walker.nextNode())){if(n.parentNode.closest('button'))continue;nodes.push(n);}
    nodes.forEach(function(node){
      var text=node.nodeValue,low=text.toLowerCase(),hits=[];
      words.forEach(function(w){var i=low.indexOf(w);while(i>=0){hits.push([i,i+w.length]);i=low.indexOf(w,i+w.length);}});
      if(!hits.length)return;hits.sort(function(a,b){return a[0]-b[0];});
      var frag=document.createDocumentFragment(),pos=0;
      hits.forEach(function(h){if(h[0]<pos)return;frag.appendChild(document.createTextNode(text.slice(pos,h[0])));
        var m=document.createElement('mark');m.textContent=text.slice(h[0],h[1]);frag.appendChild(m);pos=h[1];});
      frag.appendChild(document.createTextNode(text.slice(pos)));node.parentNode.replaceChild(frag,node);
    });
  }
  var timer;
  input.addEventListener('input',function(){clearTimeout(timer);timer=setTimeout(run,120);});
  function run(){
    unmark();
    var q=input.value.trim().toLowerCase(),words=q.split(/\s+/).filter(Boolean),shown=0;
    blocks.forEach(function(b){
      var ok=!words.length||words.every(function(w){return b._text.indexOf(w)>=0;});
      b.classList.toggle('hidden',!ok);if(ok&&words.length){shown++;markIn(b,words);}
    });
    // a section heading stays when anything below it matches
    document.querySelectorAll('main section').forEach(function(s){
      var any=[].some.call(s.querySelectorAll('.block'),function(b){return !b.classList.contains('hidden');});
      s.classList.toggle('hidden',!any);
    });
    Object.keys(tocLinks).forEach(function(id){
      var el=document.getElementById(id),li=tocLinks[id].closest('li');
      // a section (h2) stays listed while anything inside it matches; a part (h3) when its own block does
      var vis=el&&(el.tagName==='H2'?!el.closest('section').classList.contains('hidden'):!el.closest('.hidden'));
      if(li)li.classList.toggle('hide',!vis);
      if(words.length&&vis){var d=li&&li.closest('details');if(d)d.open=true;}
    });
    count.textContent=words.length?(shown+' matching part'+(shown===1?'':'s')):'';
    none.style.display=words.length&&!shown?'block':'none';
  }
  document.addEventListener('keydown',function(e){
    if(e.key==='/'&&document.activeElement!==input){e.preventDefault();input.focus();input.select();}
    else if(e.key==='Escape'&&document.activeElement===input){input.value='';run();input.blur();}
  });
  // highlight where you are in the contents
  var heads=[].slice.call(document.querySelectorAll('main h2[id],main h3[id]'));
  if('IntersectionObserver' in window){
    var current;var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){
      if(current)current.classList.remove('on');current=tocLinks[e.target.id];if(current)current.classList.add('on');}});},{rootMargin:'0px 0px -75% 0px'});
    heads.forEach(function(h){io.observe(h);});
  }
  // mobile menu
  var nav=document.querySelector('nav');document.getElementById('menu').addEventListener('click',function(){nav.classList.toggle('open');});
  nav.addEventListener('click',function(e){if(e.target.tagName==='A'&&innerWidth<=900)nav.classList.remove('open');});
  document.getElementById('expand').addEventListener('click',function(){var d=document.querySelectorAll('.toc details'),open=[].some.call(d,function(x){return !x.open;});d.forEach(function(x){x.open=open;});});
})();
"""


def build(md):
    # the Markdown's own "Contents" list repeats the sidebar: leave it out
    md = re.sub(r"(?ms)^## Contents\n.*?(?=^---$|^## )", "", md, count=1)
    blocks = convert(md)
    title, version = "LibESQL API Reference", ""
    m = re.search(r"^Version ([^\n]+)$", md, re.M)
    if m:
        version = re.sub(r"`", "", m.group(1)).split()[0]   # "1.0.0"

    # group: h2 sections, each split into blocks (intro + one per h3)
    body, toc = [], []
    in_section = in_block = False
    sec_items = None

    def open_block():
        nonlocal in_block
        body.append('<div class="block">')
        in_block = True

    def close_block():
        nonlocal in_block
        if in_block:
            body.append("</div>")
            in_block = False

    for b in blocks:
        if b[0] == "h":
            _, level, text, slug = b
            h_html = '<h%d id="%s">%s<a class="anchor" href="#%s" aria-label="Link to this part">#</a></h%d>' % (
                level, slug, inline(text), slug, level)
            if level == 1:
                body.append('<h1 id="%s">%s</h1>' % (slug, inline(text)))
                continue
            if level == 2:
                close_block()
                if in_section:
                    body.append("</section>")
                body.append("<section>")
                in_section = True
                open_block()
                body.append(h_html)
                sec_items = []
                toc.append([slug, text, sec_items])
                continue
            if level == 3:
                close_block()
                open_block()
                body.append(h_html)
                if sec_items is not None:
                    sec_items.append([slug, text])
                continue
            body.append(h_html)
            continue
        if not in_block:
            open_block()
        body.append(b[1])
    close_block()
    if in_section:
        body.append("</section>")

    toc_html = ['<ul class="toc">']
    for slug, text, items in toc:
        plain = html.escape(re.sub(r"[`*]", "", text))
        if items:
            toc_html.append('<li><details><summary><a href="#%s">%s</a></summary><ul>' % (slug, plain))
            for s2, t2 in items:
                toc_html.append('<li><a href="#%s">%s</a></li>' % (s2, html.escape(re.sub(r"[`*]", "", t2))))
            toc_html.append("</ul></details></li>")
        else:
            toc_html.append('<li><a href="#%s">%s</a></li>' % (slug, plain))
    toc_html.append("</ul>")

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="LibESQL for Elder Scrolls Online: every function, the SQL dialect and every table.">
<style>%(css)s</style>
</head>
<body>
<button class="menu" id="menu" type="button">Contents</button>
<div class="layout">
<nav aria-label="Contents">
<h1>LibESQL</h1>
<div class="ver">API Reference%(ver)s</div>
<div class="search"><input id="q" type="search" placeholder="Search functions, tables, columns" aria-label="Search the reference" autocomplete="off"><kbd>/</kbd></div>
<div class="count" id="count" aria-live="polite"></div>
%(toc)s
<div class="tools"><button type="button" id="expand">Open / close all</button><button type="button" id="theme">Light / dark</button></div>
</nav>
<main>
%(body)s
<p class="none" id="none">Nothing matches. Try fewer or shorter words.</p>
<footer>Generated from API Reference.md by tools/make_api_html.py. MIT licensed.</footer>
</main>
</div>
<script>%(js)s</script>
</body>
</html>
""" % {
        "title": html.escape(title), "css": CSS, "js": JS, "toc": "\n".join(toc_html),
        "body": "\n".join(body), "ver": (" &middot; " + html.escape(version)) if version else "",
    }


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else SRC
    out = sys.argv[2] if len(sys.argv) > 2 else OUT
    with open(src, encoding="utf-8") as f:
        md = f.read()
    page = build(md)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print("Wrote %s (%.0f KB)" % (out, len(page.encode("utf-8")) / 1024))


if __name__ == "__main__":
    main()
