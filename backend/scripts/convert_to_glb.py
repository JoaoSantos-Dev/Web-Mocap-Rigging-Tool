import sys
import traceback
from pathlib import Path

import bpy
from mathutils import Vector


def read_args() -> tuple[Path, Path]:
    if "--" not in sys.argv:
        raise ValueError("Argumentos ausentes. Use: -- input_path output_path")

    args = sys.argv[sys.argv.index("--") + 1 :]
    if len(args) != 2:
        raise ValueError("Informe exatamente input_path e output_path.")

    return Path(args[0]).resolve(), Path(args[1]).resolve()


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_model(input_path: Path) -> None:
    extension = input_path.suffix.lower()

    if extension == ".obj":
        try:
            bpy.ops.wm.obj_import(filepath=str(input_path))
        except Exception:
            bpy.ops.import_scene.obj(filepath=str(input_path))
        return

    if extension == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(input_path))
        return

    if extension in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(input_path))
        return

    raise ValueError(f"Extensão não suportada: {extension}")


def mesh_bounds() -> tuple[Vector, Vector] | None:
    points = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))

    if not points:
        return None

    min_point = Vector(
        (
            min(point.x for point in points),
            min(point.y for point in points),
            min(point.z for point in points),
        )
    )
    max_point = Vector(
        (
            max(point.x for point in points),
            max(point.y for point in points),
            max(point.z for point in points),
        )
    )
    return min_point, max_point


def center_model() -> None:
    bounds = mesh_bounds()
    if bounds is None:
        return

    min_point, max_point = bounds
    center = (min_point + max_point) * 0.5

    for obj in bpy.context.scene.objects:
        if obj.parent is None:
            obj.location -= center

    bpy.context.view_layer.update()


def export_glb(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(output_path),
        export_format="GLB",
    )


def main() -> None:
    input_path, output_path = read_args()
    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {input_path}")

    clear_scene()
    import_model(input_path)
    center_model()
    export_glb(output_path)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
