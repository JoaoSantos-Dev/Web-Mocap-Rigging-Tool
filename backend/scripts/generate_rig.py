import json
import sys
import traceback
from pathlib import Path

import bpy
from mathutils import Vector


REQUIRED_MARKERS = {
    "chin",
    "pelvis",
    "leftShoulder",
    "rightShoulder",
    "leftElbow",
    "rightElbow",
    "leftWrist",
    "rightWrist",
    "leftKnee",
    "rightKnee",
    "leftAnkle",
    "rightAnkle",
}


def read_args() -> tuple[Path, Path, Path, str]:
    if "--" not in sys.argv:
        raise ValueError(
            "Argumentos ausentes. Use: -- input_model_path markers_json_path output_path export_format"
        )

    args = sys.argv[sys.argv.index("--") + 1 :]
    if len(args) != 4:
        raise ValueError(
            "Informe exatamente input_model_path, markers_json_path, output_path e export_format."
        )

    export_format = args[3].lower()
    if export_format not in {"glb", "fbx"}:
        raise ValueError("export_format deve ser 'glb' ou 'fbx'.")

    return Path(args[0]).resolve(), Path(args[1]).resolve(), Path(args[2]).resolve(), export_format


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_model(input_model_path: Path) -> None:
    if not input_model_path.exists():
        raise FileNotFoundError(f"Modelo de entrada não encontrado: {input_model_path}")

    if input_model_path.suffix.lower() != ".glb":
        raise ValueError("A Fase 2 espera um modelo GLB já convertido pela Fase 1.")

    bpy.ops.import_scene.gltf(filepath=str(input_model_path))


def convert_marker_to_blender_space(marker: dict[str, float]) -> Vector:
    """Converte Three.js/glTF Y-up para o espaço interno Z-up do Blender.

    O GLB gerado na Fase 1 é visualizado no Three.js em coordenadas glTF
    com Y como eixo vertical. Quando esse GLB é importado no Blender, o
    importador converte para o sistema Z-up. A conversão compatível é:
    Three/glTF (x, y, z) -> Blender (x, -z, y).
    """

    return Vector((float(marker["x"]), -float(marker["z"]), float(marker["y"])))


def load_markers(markers_json_path: Path) -> dict[str, Vector]:
    if not markers_json_path.exists():
        raise FileNotFoundError(f"JSON de marcadores não encontrado: {markers_json_path}")

    with markers_json_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    raw_markers = payload.get("markers", payload)
    missing = sorted(REQUIRED_MARKERS - set(raw_markers))
    if missing:
        raise ValueError(f"Marcadores obrigatórios ausentes: {', '.join(missing)}")

    return {
        name: convert_marker_to_blender_space(raw_markers[name])
        for name in REQUIRED_MARKERS
    }


def midpoint(a: Vector, b: Vector) -> Vector:
    return (a + b) * 0.5


def safe_direction(vector: Vector, fallback: Vector) -> Vector:
    if vector.length < 0.00001:
        return fallback.normalized()
    return vector.normalized()


def ensure_tail(head: Vector, tail: Vector, fallback: Vector, minimum_length: float) -> Vector:
    if (tail - head).length >= minimum_length:
        return tail
    return head + safe_direction(fallback, Vector((0, 0, 1))) * minimum_length


def build_bone_points(markers: dict[str, Vector]) -> tuple[dict[str, tuple[Vector, Vector]], float]:
    pelvis = markers["pelvis"]
    chin = markers["chin"]
    left_shoulder = markers["leftShoulder"]
    right_shoulder = markers["rightShoulder"]
    left_elbow = markers["leftElbow"]
    right_elbow = markers["rightElbow"]
    left_wrist = markers["leftWrist"]
    right_wrist = markers["rightWrist"]
    left_knee = markers["leftKnee"]
    right_knee = markers["rightKnee"]
    left_ankle = markers["leftAnkle"]
    right_ankle = markers["rightAnkle"]

    shoulder_mid = midpoint(left_shoulder, right_shoulder)
    ankle_mid = midpoint(left_ankle, right_ankle)
    body_height = max((chin - ankle_mid).length, 1.0)
    min_length = body_height * 0.025
    up = Vector((0, 0, 1))
    forward = Vector((0, -1, 0))

    spine_tail = shoulder_mid.lerp(pelvis, 0.22)
    hips_tail = pelvis.lerp(spine_tail, 0.25)
    neck_tail = shoulder_mid.lerp(chin, 0.5)
    head_tail = chin + up * max(body_height * 0.08, min_length)

    shoulder_width = max((left_shoulder - right_shoulder).length, min_length)
    knee_width = max(abs(left_knee.x - right_knee.x), min_length)
    left_sign = -1 if left_knee.x <= right_knee.x else 1
    hip_offset = max(knee_width * 0.45, shoulder_width * 0.18, min_length)
    left_hip = pelvis + Vector((left_sign * hip_offset, 0, 0))
    right_hip = pelvis - Vector((left_sign * hip_offset, 0, 0))

    left_hand_direction = safe_direction(left_wrist - left_elbow, Vector((-1, 0, 0)))
    right_hand_direction = safe_direction(right_wrist - right_elbow, Vector((1, 0, 0)))
    hand_length = max(body_height * 0.06, min_length)
    foot_length = max(body_height * 0.08, min_length)

    bones = {
        "Hips": (pelvis, hips_tail),
        "Spine": (pelvis, spine_tail),
        "Chest": (spine_tail, shoulder_mid),
        "Neck": (shoulder_mid, neck_tail),
        "Head": (neck_tail, head_tail),
        "LeftUpperArm": (left_shoulder, left_elbow),
        "LeftLowerArm": (left_elbow, left_wrist),
        "LeftHand": (left_wrist, left_wrist + left_hand_direction * hand_length),
        "RightUpperArm": (right_shoulder, right_elbow),
        "RightLowerArm": (right_elbow, right_wrist),
        "RightHand": (right_wrist, right_wrist + right_hand_direction * hand_length),
        "LeftUpperLeg": (left_hip, left_knee),
        "LeftLowerLeg": (left_knee, left_ankle),
        "LeftFoot": (left_ankle, left_ankle + forward * foot_length),
        "RightUpperLeg": (right_hip, right_knee),
        "RightLowerLeg": (right_knee, right_ankle),
        "RightFoot": (right_ankle, right_ankle + forward * foot_length),
    }

    cleaned_bones = {
        name: (head, ensure_tail(head, tail, tail - head, min_length))
        for name, (head, tail) in bones.items()
    }
    return cleaned_bones, min_length


def create_armature(bone_points: dict[str, tuple[Vector, Vector]]) -> bpy.types.Object:
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    armature = bpy.context.object
    armature.name = "Humanoid_Armature"
    armature.data.name = "Humanoid_Armature_Data"
    armature.show_in_front = True

    edit_bones = armature.data.edit_bones
    for bone in list(edit_bones):
        edit_bones.remove(bone)

    parents = {
        "Hips": None,
        "Spine": "Hips",
        "Chest": "Spine",
        "Neck": "Chest",
        "Head": "Neck",
        "LeftUpperArm": "Chest",
        "LeftLowerArm": "LeftUpperArm",
        "LeftHand": "LeftLowerArm",
        "RightUpperArm": "Chest",
        "RightLowerArm": "RightUpperArm",
        "RightHand": "RightLowerArm",
        "LeftUpperLeg": "Hips",
        "LeftLowerLeg": "LeftUpperLeg",
        "LeftFoot": "LeftLowerLeg",
        "RightUpperLeg": "Hips",
        "RightLowerLeg": "RightUpperLeg",
        "RightFoot": "RightLowerLeg",
    }

    connect_to_parent = {
        "Chest",
        "Neck",
        "Head",
        "LeftLowerArm",
        "LeftHand",
        "RightLowerArm",
        "RightHand",
        "LeftLowerLeg",
        "LeftFoot",
        "RightLowerLeg",
        "RightFoot",
    }

    created = {}
    for name, parent_name in parents.items():
        head, tail = bone_points[name]
        bone = edit_bones.new(name)
        bone.head = head
        bone.tail = tail
        bone.use_deform = True
        if parent_name:
            bone.parent = created[parent_name]
            bone.use_connect = name in connect_to_parent and (bone.head - bone.parent.tail).length < 0.0001
        created[name] = bone

    bpy.ops.object.mode_set(mode="OBJECT")
    return armature


def distance_to_segment(point: Vector, start: Vector, end: Vector) -> float:
    segment = end - start
    if segment.length_squared < 0.0000001:
        return (point - start).length

    factor = max(0.0, min(1.0, (point - start).dot(segment) / segment.length_squared))
    closest = start + segment * factor
    return (point - closest).length


def bind_meshes_to_armature(armature: bpy.types.Object) -> None:
    bone_segments = {
        bone.name: (
            armature.matrix_world @ bone.head_local,
            armature.matrix_world @ bone.tail_local,
        )
        for bone in armature.data.bones
        if bone.use_deform
    }

    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    for obj in mesh_objects:
        matrix_world = obj.matrix_world.copy()
        groups = {name: obj.vertex_groups.new(name=name) for name in bone_segments}
        assignments = {name: [] for name in bone_segments}

        for vertex in obj.data.vertices:
            world_point = matrix_world @ vertex.co
            closest_name = min(
                bone_segments,
                key=lambda name: distance_to_segment(world_point, *bone_segments[name]),
            )
            assignments[closest_name].append(vertex.index)

        for name, indices in assignments.items():
            if indices:
                groups[name].add(indices, 1.0, "REPLACE")

        modifier = obj.modifiers.new(name="Humanoid_Armature", type="ARMATURE")
        modifier.object = armature
        obj.parent = armature
        obj.matrix_world = matrix_world


def export_scene(output_path: Path, export_format: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")

    if export_format == "glb":
        try:
            bpy.ops.export_scene.gltf(
                filepath=str(output_path),
                export_format="GLB",
                export_skins=True,
                export_animations=False,
            )
        except TypeError:
            bpy.ops.export_scene.gltf(
                filepath=str(output_path),
                export_format="GLB",
            )
        return

    try:
        bpy.ops.export_scene.fbx(
            filepath=str(output_path),
            use_selection=False,
            object_types={"ARMATURE", "MESH"},
            axis_forward="-Z",
            axis_up="Y",
            add_leaf_bones=False,
            bake_anim=False,
            use_armature_deform_only=True,
        )
    except TypeError:
        bpy.ops.export_scene.fbx(
            filepath=str(output_path),
            use_selection=False,
            object_types={"ARMATURE", "MESH"},
            axis_forward="-Z",
            axis_up="Y",
            add_leaf_bones=False,
            bake_anim=False,
        )


def main() -> None:
    input_model_path, markers_json_path, output_path, export_format = read_args()

    clear_scene()
    import_model(input_model_path)
    markers = load_markers(markers_json_path)
    bone_points, _ = build_bone_points(markers)
    armature = create_armature(bone_points)
    bind_meshes_to_armature(armature)
    export_scene(output_path, export_format)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
