import re, pathlib, json, collections

root = pathlib.Path(r"C:\Users\manid\Downloads\project\frontend\src")

jsx_classes = collections.Counter()
files_by_class = collections.defaultdict(set)

attr_re = re.compile(r'className=\{?["\'`]([^"\'`]*)["\'`]\}?')
# handle template literals with ${...} too
tmpl_re = re.compile(r'className=\{`([^`]*)`\}')

for f in root.rglob("*.jsx"):
    text = f.read_text(encoding="utf-8", errors="replace")
    for m in attr_re.finditer(text):
        raw = m.group(1)
        for tok in re.split(r'\s+', raw):
            tok = tok.strip()
            if tok and not tok.startswith("${"):
                jsx_classes[tok] += 1
                files_by_class[tok].add(f.name)
    for m in tmpl_re.finditer(text):
        raw = m.group(1)
        # strip ${...} expressions but keep literal parts
        literal = re.sub(r'\$\{[^}]*\}', ' ', raw)
        for tok in re.split(r'\s+', literal):
            tok = tok.strip()
            if tok:
                jsx_classes[tok] += 1
                files_by_class[tok].add(f.name)

css_text = (root / "styles.css").read_text(encoding="utf-8", errors="replace")
css_classes = set(re.findall(r'\.([A-Za-z][\w-]*)', css_text))

used = set(jsx_classes)
missing = sorted(c for c in used if c not in css_classes)

print(f"distinct jsx classes: {len(used)}")
print(f"css classes defined: {len(css_classes)}")
print(f"MISSING FROM CSS: {len(missing)}")
for c in missing:
    print(f"  {c:34s} {sorted(files_by_class[c])}")
