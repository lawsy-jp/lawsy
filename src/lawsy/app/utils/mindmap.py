from streamlit_markmap import markmap


def draw_mindmap(mindmap: str):
    data = f"""
---
markmap:
  pan: false
  zoom: false
---

{mindmap}
"""
    return markmap(data, height=400)
