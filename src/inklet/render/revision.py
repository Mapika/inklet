"""Compare completed bundles without modifying the previous revision."""
import hashlib
import json
from pathlib import Path
import shutil


def stage_revision(compare_to, stage, files, metadata, name):
    """Stage a prior PNG and metadata; compare pixels only on matching canvases."""
    from PIL import Image, ImageChops
    source = Path(compare_to).resolve()
    if source.is_dir(): source = source/f'{name}-manifest.json'
    previous = json.loads(source.read_text(encoding='utf-8'))
    filename = previous['files']['png']
    if not isinstance(filename,str) or Path(filename).name != filename or filename in ('.','..'):
        raise ValueError('comparison manifest PNG must be a local filename')
    preview = source.parent/filename
    # Decode before copying, so malformed prior revisions cannot replace a good bundle.
    with Image.open(preview) as image: image.verify()
    files['previous_png'] = f'{name}-previous.png'
    files['previous_manifest'] = f'{name}-previous-manifest.json'
    shutil.copyfile(preview,stage/files['previous_png'])
    snapshot = dict(previous, files={'png':files['previous_png']},
                    source_manifest_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    snapshot.pop('revision',None)
    (stage/files['previous_manifest']).write_text(json.dumps(snapshot,indent=2)+'\n',encoding='utf-8')
    revision = dict(previous_name=previous.get('name','Previous revision'),
                    previous_width_mm=previous['width_mm'], previous_height_mm=previous['height_mm'],
                    previous_dpi=previous['dpi'], previous_png_sha256=hashlib.sha256(preview.read_bytes()).hexdigest())
    physical_match = all(abs(float(previous[k])-metadata[k])<1e-6 for k in ('width_mm','height_mm','dpi'))
    with Image.open(preview) as a, Image.open(stage/files['png']) as b:
        comparable = physical_match and a.size == b.size
        revision['pixel_comparable'] = comparable
        if comparable:
            def opaque(image):
                rgba=image.convert('RGBA')
                return Image.alpha_composite(Image.new('RGBA',rgba.size,'white'),rgba).convert('RGB')
            diff=ImageChops.difference(opaque(a),opaque(b))
            r,g,blue=diff.split()
            mask=ImageChops.lighter(ImageChops.lighter(r,g),blue)
            revision['changed_fraction']=sum(mask.histogram()[26:])/(a.width*a.height)
            revision['channel_threshold']=25
            files['revision_diff']=f'{name}-revision-diff.png'
            diff.point(lambda p:min(255,p*5)).save(stage/files['revision_diff'])
        else:
            revision['comparison_note']='Page dimensions, preview resolution or pixel dimensions changed; shown side by side without a pixel score.'
    metadata['revision']=revision
