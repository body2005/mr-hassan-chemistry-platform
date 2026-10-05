"""Install a pinned QA-only local OCR candidate outside the application image.

Run in a disposable container with /qa-paddle as its only writable host mount.
No application environment, credentials, database or Docker socket is needed.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.request


root = Path('/qa-paddle')
python = root / 'venv/bin/python'
if not python.exists():
    subprocess.run([sys.executable, '-m', 'venv', '--system-site-packages', str(root/'venv')], check=True)
subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check',
                'paddlepaddle==3.2.0', 'paddleocr==3.3.2', 'paddlex==3.3.13'], check=True)
archive = root/'arabic_PP-OCRv5_mobile_rec_infer.tar'
url = ('https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/'
       'paddle3.0.0/arabic_PP-OCRv5_mobile_rec_infer.tar')
if not archive.exists():
    urllib.request.urlretrieve(url, archive)
model = root/'arabic_PP-OCRv5_mobile_rec_infer'
if not model.exists():
    with tarfile.open(archive) as stream:
        stream.extractall(root, filter='data')
if not model.is_dir():
    raise RuntimeError('Unexpected model archive layout')
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
if digest != 'a25c1f96cd0cda485b942851b5afb4a95bc4041a56c295bb4439190d53ee0a14':
    raise RuntimeError('QA model archive does not match the reviewed publisher download')
(root/'model-provenance.json').write_text(json.dumps({
    'publisher_url': url, 'sha256': digest, 'paddlepaddle': '3.2.0', 'paddleocr': '3.3.2', 'paddlex': '3.3.13'
}, indent=2))
print(json.dumps({'model_sha256': digest}))
