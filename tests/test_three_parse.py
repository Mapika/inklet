"""The three hand-written mesh readers, round-tripped against one known shape.

Every test here uses the same tetrahedron: four vertices, four faces, no
symmetry that could hide an axis swap, and small enough to write out by hand in
each format. A reader that loses a face, transposes y and z, or drops the last
line of a file fails on it, and those are the three things mesh readers
actually get wrong.

The files are written by the tests rather than committed. A committed binary
fixture is a thing nobody can review in a diff, and the interesting property --
"this byte layout means this geometry" -- is clearer as the code that produced
it.
"""

from __future__ import annotations

import struct

import pytest

from inklet.three import Mesh, MeshError, Vec3, load, sniff, supported_formats
from inklet.three.parse import (
    NATIVE_FORMATS, load_obj, load_ply, load_stl, repaired,
)

# An irregular tetrahedron. Distinct coordinates on every axis, so a reader
# that swaps two of them produces a different shape rather than the same one.
CORNERS = (Vec3(0.0, 0.0, 0.0), Vec3(2.0, 0.0, 0.0),
           Vec3(0.0, 3.0, 0.0), Vec3(0.0, 0.0, 5.0))
FACES = ((0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3))
TETRAHEDRON = Mesh(CORNERS, FACES)


def same_shape(mesh: Mesh, expected: Mesh = TETRAHEDRON) -> bool:
    """Compare by geometry, not by index: a reader that welds vertices in a
    different order is still correct, one that moves them is not."""
    def triangles(m):
        return sorted(tuple(sorted(m.vertices[i].as_tuple() for i in face))
                      for face in m.faces)

    return triangles(mesh) == triangles(expected)


# -- OBJ ------------------------------------------------------------------


OBJ = """\
# a tetrahedron
v 0 0 0
v 2 0 0
v 0 3 0
v 0 0 5
vn 0 0 -1
f 1 3 2
f 1 2 4
f 1 4 3
f 2 3 4
"""


def test_obj_round_trips():
    assert same_shape(load_obj(OBJ.encode()))


def test_obj_accepts_index_triples_and_negative_indices():
    body = OBJ.replace("f 1 3 2", "f 1/1/1 3/2/1 2/3/1").replace("f 2 3 4", "f -3 -2 -1")
    assert same_shape(load_obj(body.encode()))


def test_obj_fan_triangulates_a_quad():
    quad = "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 4\n"
    assert len(load_obj(quad.encode()).faces) == 2


def test_obj_groups_become_face_names():
    body = "v 0 0 0\nv 1 0 0\nv 0 1 0\ng lid\nf 1 2 3\n"
    assert load_obj(body.encode()).group_names == ("lid",)


def test_obj_errors_name_the_file_and_the_line():
    body = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 9\n"
    with pytest.raises(MeshError, match=r"model\.obj:4:.*out of range"):
        load_obj(body.encode(), "model.obj")


def test_obj_refuses_a_record_it_does_not_understand():
    # Silence here is the dangerous failure: a curve record read as nothing
    # gives a mesh that is missing a piece and says so nowhere.
    with pytest.raises(MeshError, match="unknown OBJ record 'curv'"):
        load_obj(b"v 0 0 0\ncurv 0 1 1 2\n")


def test_obj_rejects_the_1_based_index_zero():
    with pytest.raises(MeshError, match="1-based"):
        load_obj(b"v 0 0 0\nv 1 0 0\nv 0 1 0\nf 0 1 2\n")


# -- STL ------------------------------------------------------------------


def ascii_stl(mesh: Mesh) -> bytes:
    out = ["solid tetra"]
    for face, normal in zip(mesh.faces, mesh.face_normals):
        out.append(f"  facet normal {normal.x} {normal.y} {normal.z}")
        out.append("    outer loop")
        for i in face:
            v = mesh.vertices[i]
            out.append(f"      vertex {v.x} {v.y} {v.z}")
        out.append("    endloop")
        out.append("  endfacet")
    out.append("endsolid tetra")
    return "\n".join(out).encode()


def binary_stl(mesh: Mesh) -> bytes:
    out = [b"\0" * 80, struct.pack("<I", len(mesh.faces))]
    for face, n in zip(mesh.faces, mesh.face_normals):
        values = [n.x, n.y, n.z]
        for i in face:
            values += list(mesh.vertices[i].as_tuple())
        out.append(struct.pack("<12fH", *values, 0))
    return b"".join(out)


def test_ascii_stl_round_trips():
    assert same_shape(load_stl(ascii_stl(TETRAHEDRON)))


def test_binary_stl_round_trips():
    assert same_shape(load_stl(binary_stl(TETRAHEDRON)))


def test_binary_stl_welds_repeated_corners():
    # STL has no index list, so a naive reader yields 3 vertices per facet.
    # Welding is what makes the edge table -- and therefore every silhouette
    # test downstream -- see a closed solid instead of four loose triangles.
    mesh = load_stl(binary_stl(TETRAHEDRON))
    assert len(mesh.vertices) == 4
    assert mesh.is_closed


def test_stl_is_recognised_by_content_not_by_extension():
    # The trap this exists for: a binary STL whose 80-byte header happens to
    # begin with the word "solid", which is common and which fools every
    # reader that tests the prefix first.
    raw = binary_stl(TETRAHEDRON)
    lying = b"solid exported from cad tool ".ljust(80, b"\0") + raw[80:]
    assert sniff(lying) == "stl"
    assert same_shape(load_stl(lying))


def test_ascii_stl_truncated_mid_facet_is_an_error():
    body = ascii_stl(TETRAHEDRON).split(b"endloop")[0]
    with pytest.raises(MeshError, match="unterminated"):
        load_stl(body)


def test_ascii_stl_with_a_four_vertex_loop_is_an_error():
    body = ascii_stl(TETRAHEDRON).replace(
        b"    endloop", b"      vertex 9 9 9\n    endloop", 1)
    with pytest.raises(MeshError, match="triangles"):
        load_stl(body)


def test_sniffing_an_ascii_stl_and_an_obj():
    assert sniff(ascii_stl(TETRAHEDRON)) == "stl"
    assert sniff(OBJ.encode()) == "obj"


# -- PLY ------------------------------------------------------------------


def ascii_ply(mesh: Mesh) -> bytes:
    head = [
        "ply", "format ascii 1.0",
        f"element vertex {len(mesh.vertices)}",
        "property float x", "property float y", "property float z",
        f"element face {len(mesh.faces)}",
        "property list uchar int vertex_indices",
        "end_header",
    ]
    body = [f"{v.x} {v.y} {v.z}" for v in mesh.vertices]
    body += [f"3 {a} {b} {c}" for a, b, c in mesh.faces]
    return ("\n".join(head + body) + "\n").encode()


def binary_ply(mesh: Mesh) -> bytes:
    head = ascii_ply(mesh).split(b"end_header")[0]
    head = head.replace(b"format ascii 1.0", b"format binary_little_endian 1.0")
    out = [head + b"end_header\n"]
    for v in mesh.vertices:
        out.append(struct.pack("<3f", *v.as_tuple()))
    for face in mesh.faces:
        out.append(struct.pack("<B3i", 3, *face))
    return b"".join(out)


def test_ascii_ply_round_trips():
    assert same_shape(load_ply(ascii_ply(TETRAHEDRON)))


def test_binary_little_endian_ply_round_trips():
    assert same_shape(load_ply(binary_ply(TETRAHEDRON)))


def test_ply_triangulates_a_polygon_face():
    body = ascii_ply(TETRAHEDRON).replace(b"element face 4", b"element face 1")
    body = body.split(b"3 0 2 1")[0] + b"4 0 1 2 3\n"
    assert len(load_ply(body).faces) == 2


def test_ply_ignores_properties_it_does_not_need():
    # Real files carry normals, colours and confidence values interleaved with
    # the coordinates. Skipping by declared width is the only way to stay in
    # step with the record layout.
    body = ascii_ply(TETRAHEDRON)
    body = body.replace(b"property float z\n",
                        b"property float z\nproperty uchar red\n"
                        b"property uchar green\nproperty uchar blue\n")
    for x, y, z in ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0),
                    (0.0, 3.0, 0.0), (0.0, 0.0, 5.0)):
        body = body.replace(f"{x} {y} {z}\n".encode(),
                            f"{x} {y} {z} 10 20 30\n".encode())
    assert same_shape(load_ply(body))


def test_ply_big_endian_is_refused_rather_than_read_wrong():
    body = binary_ply(TETRAHEDRON).replace(b"binary_little_endian",
                                           b"binary_big_endian")
    with pytest.raises(MeshError, match="big.endian|big_endian"):
        load_ply(body)


def test_ply_without_a_header_terminator_is_an_error():
    body = ascii_ply(TETRAHEDRON).split(b"end_header")[0]
    with pytest.raises(MeshError, match="end_header"):
        load_ply(body)


def test_ply_truncated_body_is_an_error():
    body = binary_ply(TETRAHEDRON)[:-6]
    with pytest.raises(MeshError):
        load_ply(body)


# -- load() ---------------------------------------------------------------


@pytest.mark.parametrize("suffix,write", [
    (".obj", lambda m: OBJ.encode()),
    (".stl", ascii_stl),
    (".stl", binary_stl),
    (".ply", ascii_ply),
    (".ply", binary_ply),
])
def test_load_dispatches_from_content(tmp_path, suffix, write):
    file = tmp_path / f"tetra{suffix}"
    file.write_bytes(write(TETRAHEDRON))
    assert same_shape(load(file))


def test_load_names_the_mesh_after_the_file(tmp_path):
    file = tmp_path / "cortex.obj"
    file.write_text(OBJ)
    assert load(file).name == "cortex"


def test_load_of_a_missing_file_says_which_one(tmp_path):
    with pytest.raises(MeshError, match="nowhere.obj"):
        load(tmp_path / "nowhere.obj")


def test_load_of_an_empty_file_is_not_an_empty_mesh(tmp_path):
    file = tmp_path / "blank.obj"
    file.write_text("\n\n")
    with pytest.raises(MeshError, match="empty"):
        load(file)


def test_native_formats_are_always_available():
    assert set(NATIVE_FORMATS) <= set(supported_formats())


# -- the optional widening ------------------------------------------------


def test_repair_is_a_no_op_rather_than_a_failure_without_trimesh():
    # The contract for every optional accelerator in this package: absent, the
    # answer is unchanged, never missing.
    assert repaired(TETRAHEDRON).faces == TETRAHEDRON.faces


def test_repair_preserves_mesh_when_trimesh_lacks_a_lazy_dependency(monkeypatch):
    from types import SimpleNamespace
    from inklet.three import parse
    def missing(**kwargs):
        raise ModuleNotFoundError("No module named 'scipy'")
    monkeypatch.setattr(parse,'have',lambda name:True)
    monkeypatch.setattr(parse,'require',lambda name:SimpleNamespace(Trimesh=missing))
    assert parse.repaired(TETRAHEDRON) is TETRAHEDRON


def test_unknown_extension_without_trimesh_says_what_to_install(tmp_path):
    from inklet.three.deps import have

    file = tmp_path / "scene.glb"
    file.write_bytes(b"glTF\0\0\0\0")
    if have("trimesh"):
        pytest.skip("trimesh is installed, so glb is a real format here")
    with pytest.raises(MeshError, match="trimesh"):
        load(file)
