import xml.etree.ElementTree as ET
from pathlib import Path

for svg_file, fill_color in [("dark.svg", "#5EEAD4"), ("light.svg", "#0969da")]:
    p = Path(svg_file)
    if not p.exists(): continue
    
    ET.register_namespace('', "http://www.w3.org/2000/svg")
    tree = ET.parse(p)
    root = tree.getroot()
    
    # Find the text element
    # ET uses {http://www.w3.org/2000/svg} prefix for non-prefixed tags
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    el = root.find(".//*[@id='profile_views_text']", ns)
    if el is not None:
        el.set("y", "24")
        el.set("fill", fill_color)
        tree.write(p, encoding="utf-8", xml_declaration=True)
        print(f"Fixed {svg_file}")
