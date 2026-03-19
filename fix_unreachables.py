import re
from pathlib import Path

content = Path("crates/fnx-python/src/algorithms.rs").read_text()

# Pattern 1: let assignments
pattern1 = re.compile(
    r"((\s+)let \w+\s*=\s*)if gr\.is_directed\(\) \{\s+if let GraphRef::Directed \{ dg, \.\. \} = &gr \{\s+(.*?)\s+\} else \{\s+unreachable!\(\)\s+\}\s+\} else \{\s+let inner = gr\.undirected\(\);\s+(.*?)\s+\};",
    re.DOTALL
)

def repl1(m):
    indent = m.group(2)
    return (
        f"{m.group(1)}match &gr {{\n"
        f"{indent}    GraphRef::Directed {{ dg, .. }} => {{\n"
        f"{indent}        {m.group(3)}\n"
        f"{indent}    }}\n"
        f"{indent}    GraphRef::Undirected(pg) => {{\n"
        f"{indent}        let inner = &pg.inner;\n"
        f"{indent}        {m.group(4)}\n"
        f"{indent}    }}\n"
        f"{indent}}};"
    )

content = pattern1.sub(repl1, content)

# Pattern 2: Return expressions or trailing expressions (no let)
pattern2 = re.compile(
    r"(\s+)if gr\.is_directed\(\) \{\s+if let GraphRef::Directed \{ dg, \.\. \} = &gr \{\s+(.*?)\s+\} else \{\s+unreachable!\(\)\s+\}\s+\} else \{\s+let inner = gr\.undirected\(\);\s+(.*?)\s+\}",
    re.DOTALL
)

def repl2(m):
    indent = m.group(1)
    if "let " in indent: # shouldn't happen, but just in case
        return m.group(0)
    return (
        f"{indent}match &gr {{\n"
        f"{indent}    GraphRef::Directed {{ dg, .. }} => {{\n"
        f"{indent}        {m.group(2)}\n"
        f"{indent}    }}\n"
        f"{indent}    GraphRef::Undirected(pg) => {{\n"
        f"{indent}        let inner = &pg.inner;\n"
        f"{indent}        {m.group(3)}\n"
        f"{indent}    }}\n"
        f"{indent}}}"
    )

content = pattern2.sub(repl2, content)

Path("crates/fnx-python/src/algorithms.rs").write_text(content)
