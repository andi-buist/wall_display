from pathlib import Path

# create a layered dictionary reflecting the directory
def dir_to_dict(dir: Path):
    out_dict = {}

    for path in dir.rglob("*"):
        parts = path.relative_to(dir).parts
        place = out_dict

        # Walk all parts except the last
        for part in parts[:-1]:
            place = place.setdefault(part, {})
        last = parts[-1]
        if path.is_dir():
            place.setdefault(last, {})
        else:
            place[last.split(".")[0]] = path
    
    return out_dict

global_font = ('Nintendo DS BIOS', 12)
global_qss = Path('stylesheet.qss')
filestore = dir_to_dict(Path("theme"))