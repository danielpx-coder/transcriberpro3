from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
root = Path(__file__).resolve().parents[1]
output = root / 'dist/transcriberpro3-wordpress.zip'
output.parent.mkdir(exist_ok=True)
files = [root / 'transcriberpro3.php', *sorted((root / 'assets').glob('*'))]
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for file in files:
        archive.write(file, 'transcriberpro3/' + str(file.relative_to(root)))
print(output)
