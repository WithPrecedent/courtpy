# Catalog

This page lists courtpy's techniques and the columns that its rulebooks make.
It is built from courtpy itself each time the documentation is built, so it
is always current. A study's settings can name any of these techniques (see
[Building a Study](studies.md)).

## Techniques

```python exec="on"
import inspect

import amos
import chrisjen
import courtpy  # noqa: F401  (adds courtpy's techniques to the library)

flat = chrisjen.utilities.flatten_dict(chrisjen.library.contents)
rows = []
for key, item in flat.items():
    if not (isinstance(item, type) and item.__module__.startswith('courtpy')):
        continue
    name = key.split('.')[-1]
    # Classes in private modules (such as "judges._panels") are documented
    # under their public module.
    module = '.'.join(
        part for part in item.__module__.split('.')
        if not part.startswith('_'))
    summary = (inspect.getdoc(item) or '').split('\n')[0]
    rows.append((amos.library.classify(name), name, module, summary))
print('| Genre | Technique | Module | Does |')
print('| --- | --- | --- | --- |')
for genre, name, module, summary in sorted(rows):
    print(f'| {genre} | `{name}` | `{module}` | {summary} |')
```

## Sources and ways to download

A loader's "download" (and `courtpy download`) can name any way to
download, and `courtpy parse --source` any source. A study can add both (see
[Building a Study](studies.md#sources-of-your-own)).

```python exec="on"
from courtpy import sources

print('| Way to download | Saves | Does |')
print('| --- | --- | --- |')
for name in sorted({c.name for c in sources.DOWNLOADS.values()}):
    method = sources.DOWNLOADS[name]
    print(f'| `{name}` | `{method.source}` | {method.describe()} |')
print()
print('| Source | Files | Does |')
print('| --- | --- | --- |')
for name, source in sorted(sources.SOURCES.items()):
    summary = (source.__doc__ or '').strip().split('\n')[0]
    print(f'| `{name}` | `{source.pattern}` | {summary} |')
```

## Rulebooks and their columns

Each rulebook below can be named in the "rulebooks" of a loader or of
`courtpy.parse`. "header" and "general" are applied to every case. The
columns of a rulebook are those that its rules make, in the order of the
rules; see the [rules guide](rules.md) for what each kind of rule makes.

```python exec="on"
import amos
from courtpy import rules

for name, book in rules.RULEBOOKS.items():
    rulebook = amos.parsers.Rulebook.create(book)
    print(f'### {name}\n')
    print(f'{(book.__doc__ or "").strip()}\n')
    if name == 'federal':
        print('Every column of the rulebooks above.\n')
        continue
    columns = ', '.join(f'`{column}`' for column in rulebook.names)
    print(f'{len(rulebook.names)} columns: {columns}\n')
```
