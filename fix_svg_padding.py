import xml.etree.ElementTree as ET
from pathlib import Path

for svg_file in ["dark.svg", "light.svg"]:
    p = Path(svg_file)
    if not p.exists(): continue
    
    ET.register_namespace('', "http://www.w3.org/2000/svg")
    tree = ET.parse(p)
    root = tree.getroot()
    
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    el = root.find(".//*[@id='profile_views_text']", ns)
    if el is not None:
        el.set("x", "24")
        el.set("y", "32")
        tree.write(p, encoding="utf-8", xml_declaration=True)
        print(f"Added margin to {svg_file}")
