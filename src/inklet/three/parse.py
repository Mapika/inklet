"""Reading meshes off disk, without asking for anything to be installed.

OBJ, STL and PLY between them cover essentially every mesh that reaches a paper
figure: OBJ from modelling tools, STL from CAD and 3D printing, PLY from
scanners and photogrammetry. All three are simple enough to parse honestly in a
few hundred lines, so `inklet.model("brain.obj")` works in a bare `pip install`.
That is the whole argument for hand-writing these.

Two rules shape the code:

**Sniff the content, never the extension.** Half the binary STLs in the world
are called `.stl` and start with the ASCII word `solid`, because the binary
format's 80-byte header is free-form and exporters write a comment into it. The
only reliable test is arithmetic: a binary STL is exactly `84 + 50n` bytes long
for the triangle count `n` in its header.

**Fail loudly, at a line number.** A mesh that silently loses a face is a
figure that is quietly wrong. Every error here names the file and, for text
formats, the line -- which is what you actually need in order to go and look.

Anything else (GLTF, COLLADA, 3MF, FBX) is handed to `trimesh` when it is
importable. That import is guarded and optional: nothing in the default path
touches it, and its absence costs you only the exotic formats.
"""

from __future__ import annotations

import struct
from pathlib import Path

from .deps import have, require
from .linalg import Vec3
from .mesh import Mesh, MeshError

__all__ = [
    "load", "load_obj", "load_stl", "load_ply", "sniff",
    "NATIVE_FORMATS", "supported_formats",
]

#: What this module reads on its own, with no optional dependency at all.
NATIVE_FORMATS = ("obj", "ply", "stl")

# Formats trimesh adds when it happens to be importable. Listed rather than
# asked of trimesh at import time, so `supported_formats()` costs nothing.
_TRIMESH_FORMATS = ("3mf", "dae", "glb", "gltf", "off", "xaml")


def supported_formats() -> tuple[str, ...]:
    """Every extension `load` will accept here and now, sorted."""
    extra = _TRIMESH_FORMATS if have("trimesh") else ()
    return tuple(sorted(NATIVE_FORMATS + extra))


def sniff(data: bytes) -> str:
    """Identify a mesh from its opening bytes and its length.

    Order matters. The binary-STL length check runs before the `solid` test
    precisely because the two disagree on real files, and PLY's magic is
    checked before OBJ's because an OBJ has no magic at all -- it is the
    fallback, and a wrong guess there produces a parse error with a line
    number rather than silence.
    """
    if data[:3] == b"ply":
        return "ply"
    if len(data) >= 84:
        count = struct.unpack_from("<I", data, 80)[0]
        if len(data) == 84 + 50 * count:
            return "stl"
    if data[:5].lower() == b"solid":
        return "stl"
    return "obj"


def load(path: str | Path, *, repair: bool = False, format: str | None = None) -> Mesh:
    """Read a mesh file.

    `format` overrides the sniffer for the rare file that lies about itself.
    `repair` asks trimesh to merge duplicate vertices and make the winding
    consistent, which is worth doing to anything downloaded: a mesh with mixed
    winding has half its normals inside out, and both the silhouette test and
    the shading read a normal's sign.
    """
    file = Path(path)
    try:
        data = file.read_bytes()
    except OSError as exc:
        raise MeshError(f"cannot read {file}: {exc}") from exc
    if not data.strip():
        raise MeshError(f"{file} is empty")

    kind = (format or _extension(file) or sniff(data)).lower()
    if kind in ("obj", "ply", "stl"):
        mesh = _NATIVE[kind](data, file)
    else:
        mesh = _via_trimesh(file, kind)
    if not mesh.faces:
        raise MeshError(f"{file} parsed cleanly but contains no triangles")
    mesh = Mesh(mesh.vertices, mesh.faces, mesh.groups, mesh.name or file.stem)
    return repaired(mesh) if repair else mesh


def _extension(file: Path) -> str | None:
    """The extension, but only when it names a format trimesh has to handle.

    For OBJ/STL/PLY the sniffer is strictly better informed than the filename,
    so it wins; for `.glb` there is nothing to sniff and the name is all there
    is.
    """
    suffix = file.suffix.lstrip(".").lower()
    return suffix if suffix in _TRIMESH_FORMATS else None


# -- OBJ ------------------------------------------------------------------


def load_obj(data: bytes, source: str | Path = "<obj>") -> Mesh:
    """Wavefront OBJ: `v`, `vn`, `vt`, `f`, `g`/`o`.

    Polygons are fan-triangulated from their first vertex. A fan is wrong for a
    concave polygon, but OBJ's own specification says faces are planar and
    convex, and the alternative -- ear clipping in 3D -- is a large amount of
    code to rescue files that are already out of spec.

    Materials are skipped, deliberately. A figure takes its colours from the
    theme, so honouring an MTL would put a modeller's choice of shiny red into
    a journal palette.
    """
    vertices: list[Vec3] = []
    faces: list[tuple[int, int, int]] = []
    groups: list[str] = []
    current = ""
    named = False

    for number, raw in enumerate(_lines(data, source), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        keyword, _, rest = line.partition(" ")
        if keyword == "v":
            vertices.append(_vertex(rest, number, source))
        elif keyword in ("g", "o"):
            current = rest.strip() or ""
            named = named or bool(current)
        elif keyword == "f":
            corners = [_obj_index(field, len(vertices), number, source)
                       for field in rest.split()]
            if len(corners) < 3:
                raise MeshError(
                    f"{source}:{number}: a face needs at least 3 vertices, "
                    f"got {len(corners)}"
                )
            for i in range(1, len(corners) - 1):
                faces.append((corners[0], corners[i], corners[i + 1]))
                groups.append(current)
        elif keyword in ("vn", "vt", "vp", "s", "usemtl", "mtllib", "l", "p"):
            continue          # known and deliberately ignored
        else:
            raise MeshError(
                f"{source}:{number}: unknown OBJ record {keyword!r}; "
                "this reader handles v, vn, vt, f, g, o, s, usemtl and mtllib"
            )
    if not vertices:
        raise MeshError(f"{source}: no vertices")
    return Mesh(tuple(vertices), tuple(faces), tuple(groups) if named else ())


def _obj_index(field: str, count: int, number: int, source) -> int:
    """One `f` corner: `v`, `v/vt`, `v//vn` or `v/vt/vn`, 1-based, possibly
    negative (counting back from the most recent vertex)."""
    text = field.split("/", 1)[0]
    try:
        index = int(text)
    except ValueError:
        raise MeshError(
            f"{source}:{number}: {field!r} is not a vertex reference") from None
    if index == 0:
        raise MeshError(f"{source}:{number}: OBJ indices are 1-based, so 0 is invalid")
    resolved = index - 1 if index > 0 else count + index
    if not 0 <= resolved < count:
        raise MeshError(
            f"{source}:{number}: vertex {index} is out of range; "
            f"{count} vertices have been declared so far"
        )
    return resolved


def _vertex(rest: str, number: int, source) -> Vec3:
    parts = rest.split()
    if len(parts) < 3:
        raise MeshError(f"{source}:{number}: a vertex needs 3 coordinates, "
                        f"got {len(parts)}")
    try:
        # A 4th component is OBJ's rational weight; nothing here is a NURBS
        # patch, so it is read past rather than divided through.
        return Vec3(float(parts[0]), float(parts[1]), float(parts[2]))
    except ValueError:
        raise MeshError(
            f"{source}:{number}: {rest.strip()!r} is not three numbers") from None


# -- STL ------------------------------------------------------------------


def load_stl(data: bytes, source: str | Path = "<stl>") -> Mesh:
    """STL in either flavour, chosen by `sniff`, never by the extension."""
    if sniff(data) != "stl":
        raise MeshError(f"{source}: does not look like an STL file")
    if len(data) >= 84:
        count = struct.unpack_from("<I", data, 80)[0]
        if len(data) == 84 + 50 * count:
            return _binary_stl(data, count, source)
    return _ascii_stl(data, source)


def _binary_stl(data: bytes, count: int, source) -> Mesh:
    """80-byte header, uint32 count, then 50 bytes per facet.

    STL has no vertex sharing at all: every triangle repeats its three corners
    in full. Welding them back together is what makes an edge map possible, and
    it is done on the exact bit pattern of the floats rather than on a
    tolerance -- an exporter that wrote the same corner twice wrote the same
    bits twice, and a tolerance here would weld a genuinely thin feature shut.
    """
    vertices: list[Vec3] = []
    faces: list[tuple[int, int, int]] = []
    index: dict[tuple[float, float, float], int] = {}
    offset = 84
    for facet in range(count):
        try:
            values = struct.unpack_from("<12fH", data, offset)
        except struct.error:
            raise MeshError(
                f"{source}: facet {facet} of {count} runs past the end of the file"
            ) from None
        offset += 50
        corners = []
        for corner in range(3):
            key = values[3 + corner * 3:6 + corner * 3]
            slot = index.get(key)
            if slot is None:
                slot = index[key] = len(vertices)
                vertices.append(Vec3(*key))
            corners.append(slot)
        faces.append((corners[0], corners[1], corners[2]))
    return Mesh(tuple(vertices), tuple(faces))


def _ascii_stl(data: bytes, source) -> Mesh:
    vertices: list[Vec3] = []
    faces: list[tuple[int, int, int]] = []
    index: dict[tuple[float, float, float], int] = {}
    pending: list[int] = []
    name = ""

    for number, raw in enumerate(_lines(data, source), start=1):
        line = raw.strip()
        if not line:
            continue
        keyword, _, rest = line.partition(" ")
        keyword = keyword.lower()
        if keyword == "vertex":
            point = _vertex(rest, number, source)
            key = point.as_tuple()
            slot = index.get(key)
            if slot is None:
                slot = index[key] = len(vertices)
                vertices.append(point)
            pending.append(slot)
        elif keyword == "endloop":
            if len(pending) != 3:
                raise MeshError(
                    f"{source}:{number}: a facet loop closed with {len(pending)} "
                    "vertices; STL facets are triangles"
                )
            faces.append((pending[0], pending[1], pending[2]))
            pending = []
        elif keyword == "solid":
            name = rest.strip()
        elif keyword in ("facet", "outer", "endfacet", "endsolid"):
            continue
        else:
            raise MeshError(f"{source}:{number}: unexpected STL record {keyword!r}")
    if pending:
        raise MeshError(f"{source}: the file ends inside an unterminated facet")
    return Mesh(tuple(vertices), tuple(faces), name=name)


# -- PLY ------------------------------------------------------------------

# PLY's scalar types, mapped to struct codes and widths. `int8`/`uint8` and the
# rest are the modern spellings; `char`/`uchar` and friends are the original
# ones and both are still emitted in the wild.
_PLY_TYPES = {
    "char": ("b", 1), "int8": ("b", 1),
    "uchar": ("B", 1), "uint8": ("B", 1),
    "short": ("h", 2), "int16": ("h", 2),
    "ushort": ("H", 2), "uint16": ("H", 2),
    "int": ("i", 4), "int32": ("i", 4),
    "uint": ("I", 4), "uint32": ("I", 4),
    "float": ("f", 4), "float32": ("f", 4),
    "double": ("d", 8), "float64": ("d", 8),
}


def load_ply(data: bytes, source: str | Path = "<ply>") -> Mesh:
    """PLY, ASCII or little-endian binary.

    Big-endian binary is refused rather than guessed at. It exists, it is rare,
    and reading it wrong produces coordinates in the 1e38 range that look like
    a corrupt file rather than like a byte-order mistake -- so the error says
    which it is.
    """
    header, body_at = _ply_header(data, source)
    if header["format"] == "binary_big_endian":
        raise MeshError(
            f"{source}: binary_big_endian PLY is not supported; re-export as "
            "ascii or binary_little_endian"
        )
    reader = _ply_ascii if header["format"] == "ascii" else _ply_binary
    return reader(data, body_at, header["elements"], source)


def _ply_header(data: bytes, source) -> tuple[dict, int]:
    end = data.find(b"end_header")
    if end < 0:
        raise MeshError(f"{source}: PLY header has no end_header")
    stop = data.find(b"\n", end)
    text = data[:end].decode("ascii", errors="replace")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "ply":
        raise MeshError(f"{source}:1: a PLY file must start with 'ply'")

    fmt: str | None = None
    elements: list[dict] = []
    for number, raw in enumerate(lines, start=1):
        parts = raw.split()
        if not parts or parts[0] == "comment" or parts[0] == "ply":
            continue
        if parts[0] == "format":
            if len(parts) < 2:
                raise MeshError(f"{source}:{number}: format needs a name")
            fmt = parts[1]
        elif parts[0] == "element":
            if len(parts) != 3:
                raise MeshError(
                    f"{source}:{number}: element needs a name and a count")
            elements.append({"name": parts[1], "count": int(parts[2]),
                             "properties": []})
        elif parts[0] == "property":
            if not elements:
                raise MeshError(
                    f"{source}:{number}: a property before any element")
            elements[-1]["properties"].append(_ply_property(parts, number, source))
        elif parts[0] == "obj_info":
            continue
        else:
            raise MeshError(f"{source}:{number}: unknown PLY header record "
                            f"{parts[0]!r}")
    if fmt not in ("ascii", "binary_little_endian", "binary_big_endian"):
        raise MeshError(f"{source}: unknown PLY format {fmt!r}")
    return {"format": fmt, "elements": elements}, stop + 1


def _ply_property(parts: list[str], number: int, source) -> dict:
    if parts[1] == "list":
        if len(parts) != 5:
            raise MeshError(
                f"{source}:{number}: a list property needs a count type, an "
                "item type and a name"
            )
        _ply_type(parts[2], number, source)
        _ply_type(parts[3], number, source)
        return {"list": True, "count_type": parts[2], "item_type": parts[3],
                "name": parts[4]}
    if len(parts) != 3:
        raise MeshError(f"{source}:{number}: a property needs a type and a name")
    _ply_type(parts[1], number, source)
    return {"list": False, "type": parts[1], "name": parts[2]}


def _ply_type(name: str, number: int, source) -> tuple[str, int]:
    try:
        return _PLY_TYPES[name]
    except KeyError:
        raise MeshError(f"{source}:{number}: unknown PLY type {name!r}") from None


def _ply_ascii(data: bytes, start: int, elements: list[dict], source) -> Mesh:
    tokens: list[str] = []
    header_lines = data[:start].count(b"\n")
    for offset, raw in enumerate(_lines(data[start:], source)):
        line = raw.strip()
        if line:
            tokens.append(line)
    cursor = 0
    vertices: list[Vec3] = []
    faces: list[tuple[int, int, int]] = []

    for element in elements:
        for row in range(element["count"]):
            if cursor >= len(tokens):
                raise MeshError(
                    f"{source}: ran out of data at {element['name']} {row} of "
                    f"{element['count']}"
                )
            number = header_lines + cursor + 1
            fields = tokens[cursor].split()
            cursor += 1
            if element["name"] == "vertex":
                vertices.append(_ply_vertex(fields, element["properties"],
                                            number, source))
            elif element["name"] == "face":
                faces.extend(_ply_face(fields, len(vertices), number, source))
    return Mesh(tuple(vertices), tuple(faces))


def _ply_vertex(fields: list[str], properties: list[dict], number: int,
                source) -> Vec3:
    if len(fields) < len(properties):
        raise MeshError(
            f"{source}:{number}: {len(fields)} values for {len(properties)} "
            "declared vertex properties"
        )
    values: dict[str, float] = {}
    for prop, text in zip(properties, fields):
        if prop["list"]:
            raise MeshError(
                f"{source}:{number}: list properties on a vertex are not read")
        try:
            values[prop["name"]] = float(text)
        except ValueError:
            raise MeshError(
                f"{source}:{number}: {text!r} is not a number") from None
    return _ply_point(values, number, source)


def _ply_point(values: dict[str, float], number: int, source) -> Vec3:
    try:
        return Vec3(values["x"], values["y"], values["z"])
    except KeyError as exc:
        raise MeshError(
            f"{source}:{number}: vertices need x, y and z; this one has "
            f"{tuple(sorted(values))} and is missing {exc.args[0]}"
        ) from None


def _ply_face(fields: list[str], count: int, number: int,
              source) -> list[tuple[int, int, int]]:
    if not fields:
        raise MeshError(f"{source}:{number}: an empty face record")
    try:
        corners = [int(f) for f in fields[1:1 + int(fields[0])]]
    except ValueError:
        raise MeshError(
            f"{source}:{number}: face indices must be integers") from None
    return _fan(corners, count, number, source)


def _fan(corners: list[int], count: int, number: int,
         source) -> list[tuple[int, int, int]]:
    if len(corners) < 3:
        raise MeshError(
            f"{source}:{number}: a face needs at least 3 vertices, "
            f"got {len(corners)}"
        )
    for i in corners:
        if not 0 <= i < count:
            raise MeshError(
                f"{source}:{number}: vertex index {i} is outside the "
                f"{count} vertices declared before it"
            )
    return [(corners[0], corners[i], corners[i + 1])
            for i in range(1, len(corners) - 1)]


def _ply_binary(data: bytes, start: int, elements: list[dict], source) -> Mesh:
    vertices: list[Vec3] = []
    faces: list[tuple[int, int, int]] = []
    offset = start

    for element in elements:
        for row in range(element["count"]):
            values: dict[str, float] = {}
            corners: list[int] = []
            for prop in element["properties"]:
                if prop["list"]:
                    length, offset = _read_scalar(data, offset, prop["count_type"],
                                                  source)
                    items = []
                    for _ in range(int(length)):
                        item, offset = _read_scalar(data, offset, prop["item_type"],
                                                    source)
                        items.append(int(item))
                    if prop["name"] in ("vertex_indices", "vertex_index"):
                        corners = items
                else:
                    value, offset = _read_scalar(data, offset, prop["type"], source)
                    values[prop["name"]] = value
            if element["name"] == "vertex":
                vertices.append(_ply_point(values, row, source))
            elif element["name"] == "face" and corners:
                faces.extend(_fan(corners, len(vertices), row, source))
    return Mesh(tuple(vertices), tuple(faces))


def _read_scalar(data: bytes, offset: int, type_name: str,
                 source) -> tuple[float, int]:
    code, width = _PLY_TYPES[type_name]
    try:
        (value,) = struct.unpack_from("<" + code, data, offset)
    except struct.error:
        raise MeshError(
            f"{source}: the binary body ends mid-value at byte {offset}"
        ) from None
    return value, offset + width


# -- shared ---------------------------------------------------------------


def _lines(data: bytes, source):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MeshError(
            f"{source}: expected a text mesh but byte {exc.start} is not UTF-8; "
            "if this is a binary file, the format sniffer did not recognise it"
        ) from None
    return text.splitlines()


_NATIVE = {"obj": load_obj, "ply": load_ply, "stl": load_stl}


# -- the optional widening ------------------------------------------------


def _via_trimesh(file: Path, kind: str) -> Mesh:
    """Formats this module does not read natively.

    Scenes are concatenated with their node names kept as face groups, because
    a GLTF's structure is exactly the thing an author wants to point an arrow
    at: `assembly.at("housing")` should work without them opening Blender.
    """
    trimesh = require("trimesh")
    try:
        loaded = trimesh.load(str(file), force=None, process=False)
    except Exception as exc:                      # trimesh raises many types
        raise MeshError(f"cannot read {file} as {kind}: {exc}") from exc
    return _from_trimesh(loaded, file)


def _from_trimesh(loaded, source) -> Mesh:
    from .mesh import merge

    if hasattr(loaded, "geometry"):               # a Scene
        parts = [_single_trimesh(geometry).grouped(name)
                 for name, geometry in sorted(loaded.geometry.items())]
        if not parts:
            raise MeshError(f"{source}: the scene contains no geometry")
        return merge(parts)
    return _single_trimesh(loaded)


def _single_trimesh(geometry) -> Mesh:
    vertices = tuple(Vec3(float(x), float(y), float(z))
                     for x, y, z in geometry.vertices.tolist())
    faces = tuple((int(a), int(b), int(c)) for a, b, c in geometry.faces.tolist())
    return Mesh(vertices, faces)


def repaired(mesh: Mesh) -> Mesh:
    """Weld duplicate vertices and make the winding consistent, via trimesh.

    Both the silhouette test and the flat shading read the *sign* of a face
    normal, so a mesh with mixed winding does not merely look odd -- it grows
    silhouette edges through the middle of flat surfaces. When trimesh is not
    installed the mesh is returned untouched and the drawing is the caller's
    problem; that is the honest fallback, since guessing a winding from scratch
    is a research problem, not a stopgap.
    """
    if not have("trimesh"):
        return mesh
    try:
        trimesh = require("trimesh")
        body = trimesh.Trimesh(
            vertices=[v.as_tuple() for v in mesh.vertices],
            faces=[list(f) for f in mesh.faces],
            process=True,
            validate=True,
        )
        trimesh.repair.fix_normals(body)
    except ImportError:
        # Trimesh imports some of its optional dependencies only when repair
        # runs. A partial installation has the same fallback as its absence.
        return mesh
    fixed = _single_trimesh(body)
    # Welding renumbers vertices, so per-face group names cannot survive it in
    # general. They do survive when the face count is unchanged, which is the
    # common case: welding a scan merges vertices, not triangles.
    groups = mesh.groups if len(fixed.faces) == len(mesh.faces) else ()
    return Mesh(fixed.vertices, fixed.faces, groups, mesh.name)
