"""Small cached axonometric views derived from IFC geometry."""
import hashlib
import math
import re
from pathlib import Path
from tempfile import NamedTemporaryFile


def thumbnail_path(root: Path, digest: str) -> Path:
    if not re.fullmatch(r'[0-9a-f]{64}', digest):
        raise ValueError('Huella IFC inválida')
    return root / '.ifc-thumbnails' / ('ax-v2-' + digest + '.svg')


def render_thumbnail(path: Path) -> str | None:
    import ifcopenshell
    import ifcopenshell.geom

    model = ifcopenshell.open(str(path))
    settings = ifcopenshell.geom.settings()
    settings.set('use-world-coords', True)
    objects = [item for item in model.by_type('IfcProduct')
               if item.Representation and not item.is_a('IfcSpace')]
    triangles = []
    limit = 7500
    # Distributed sample across the full product order (rather than always the first 24).
    # This is a representative geometric PREVIEW, not a complete geometric derivative.
    count = min(len(objects), 72)
    indices = sorted({round(i * (len(objects)-1) / max(1, count-1)) for i in range(count)})
    for index in indices:
        item = objects[index]
        try:
            shape = ifcopenshell.geom.create_shape(settings, item)
            vertices = shape.geometry.verts
            faces = shape.geometry.faces
        except RuntimeError:
            continue
        projected = [(x-y, (x+y)*.42-z, x+y+z)
                     for x,y,z in zip(vertices[::3],vertices[1::3],vertices[2::3])]
        per_object = max(30, limit // max(1, len(indices)))
        step = max(3, 3 * math.ceil((len(faces)//3) / per_object))
        stored = 0
        for start in range(0,len(faces)-2,step):
            triangle = tuple(projected[index] for index in faces[start:start+3])
            if all(math.isfinite(value) for point in triangle for value in point):
                triangles.append(triangle)
                stored += 1
            if stored >= per_object or len(triangles)>=limit:
                break
        if len(triangles)>=limit:
            break
    if not triangles:
        return None
    xs = [x for triangle in triangles for x,_,_ in triangle]
    ys = [y for triangle in triangles for _,y,_ in triangle]
    min_x,min_y=min(xs),min(ys)
    width,height=max(xs)-min_x,max(ys)-min_y
    scale=min(268/max(width,1e-9),136/max(height,1e-9))
    ox,oy=(320-width*scale)/2,(176-height*scale)/2
    polygons=[]
    for triangle in sorted(triangles,key=lambda row:sum(point[2] for point in row)):
        coords=' '.join(f'{ox+(x-min_x)*scale:.1f},{oy+(y-min_y)*scale:.1f}' for x,y,_ in triangle)
        (ax,ay,_),(bx,by,_),(cx,cy,_)=triangle
        fill='#91b1a9' if (bx-ax)*(cy-ay)-(by-ay)*(cx-ax)>0 else '#5b827a'
        polygons.append(f'<polygon points="{coords}" fill="{fill}"/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 176">'
            '<rect width="320" height="176" fill="#eaf0ee"/>'
            '<g stroke="#395c55" stroke-width=".35" stroke-linejoin="round">'
            + ''.join(polygons) + '</g></svg>')


def cache_thumbnail(root: Path, source: Path, digest: str) -> bool:
    target = thumbnail_path(root,digest)
    if source.parent!=root or not source.is_file():
        return False
    with source.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=digest:
            return False
    if target.is_file():
        return True
    svg=render_thumbnail(source)
    if svg is None:
        return False
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=None
    try:
        with NamedTemporaryFile(mode='w',encoding='utf-8',dir=target.parent,delete=False) as stream:
            temp=Path(stream.name)
            stream.write(svg)
        temp.replace(target)
    finally:
        if temp:temp.unlink(missing_ok=True)
    return True
