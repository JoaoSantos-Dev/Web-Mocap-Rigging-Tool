import json
import os
import sys
import traceback
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


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

BONE_PARENT_ORDER = {
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

CONNECTED_BONES = {
    "Spine",
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


def log(message: str) -> None:
    print(f"[generate_rig] {message}", flush=True)


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

    log(f"Importando modelo GLB: {input_model_path}")
    bpy.ops.import_scene.gltf(filepath=str(input_model_path))


def normalize_scene_transforms() -> None:
    """Coloca meshes importados em world space com transform identity.

    Isso deixa mesh e armature no mesmo espaço, reduz surpresas no FBX e
    melhora a previsibilidade da escala/rotação importada na Unity. A geometria
    recebe o matrix_world atual e os objetos mesh ficam com escala 1, rotação 0.
    """

    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    bpy.context.view_layer.update()

    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    log(f"Normalizando transforms de {len(mesh_objects)} mesh(es).")

    for obj in mesh_objects:
        world_matrix = obj.matrix_world.copy()
        obj.data = obj.data.copy()
        obj.data.transform(world_matrix)
        obj.data.update()
        obj.parent = None
        obj.matrix_world = Matrix.Identity(4)

    bpy.context.view_layer.update()


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

    markers = {
        name: convert_marker_to_blender_space(raw_markers[name])
        for name in REQUIRED_MARKERS
    }
    log("Marcadores recebidos em espaço Blender:")
    for name in sorted(markers):
        point = markers[name]
        log(f"  {name}: ({point.x:.4f}, {point.y:.4f}, {point.z:.4f})")
    return markers


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
    knee_mid = midpoint(left_knee, right_knee)
    ankle_mid = midpoint(left_ankle, right_ankle)
    body_height = max((chin - ankle_mid).length, 1.0)
    min_length = body_height * 0.025
    up = Vector((0, 0, 1))
    forward = Vector((0, -1, 0))

    spine_top = pelvis.lerp(shoulder_mid, 0.65)
    neck_tail = shoulder_mid.lerp(chin, 0.6)
    head_tail = chin + up * max(body_height * 0.08, min_length)
    hips_head = pelvis.lerp(knee_mid, 0.18)

    left_hip = pelvis.lerp(left_knee, 0.18)
    right_hip = pelvis.lerp(right_knee, 0.18)

    left_hand_direction = safe_direction(left_wrist - left_elbow, Vector((-1, 0, 0)))
    right_hand_direction = safe_direction(right_wrist - right_elbow, Vector((1, 0, 0)))
    hand_length = max(body_height * 0.055, min_length)
    foot_length = max(body_height * 0.09, min_length)

    bones = {
        "Hips": (hips_head, pelvis),
        "Spine": (pelvis, spine_top),
        "Chest": (spine_top, shoulder_mid),
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

    log("Pontos derivados da armature:")
    log(f"  shoulderCenter: ({shoulder_mid.x:.4f}, {shoulder_mid.y:.4f}, {shoulder_mid.z:.4f})")
    log(f"  spineTop: ({spine_top.x:.4f}, {spine_top.y:.4f}, {spine_top.z:.4f})")
    log(f"  neckTail: ({neck_tail.x:.4f}, {neck_tail.y:.4f}, {neck_tail.z:.4f})")
    log(f"  leftHip: ({left_hip.x:.4f}, {left_hip.y:.4f}, {left_hip.z:.4f})")
    log(f"  rightHip: ({right_hip.x:.4f}, {right_hip.y:.4f}, {right_hip.z:.4f})")
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

    created = {}
    log("Criando bones:")
    for name, parent_name in BONE_PARENT_ORDER.items():
        head, tail = bone_points[name]
        bone = edit_bones.new(name)
        bone.head = head
        bone.tail = tail
        bone.use_deform = True
        if parent_name:
            bone.parent = created[parent_name]
            can_connect = name in CONNECTED_BONES and (bone.head - bone.parent.tail).length < 0.0001
            bone.use_connect = can_connect
            if name in CONNECTED_BONES and not can_connect:
                log(f"  {name}: não conectado para preservar posição correta.")
        log(
            f"  {name}: head=({head.x:.4f}, {head.y:.4f}, {head.z:.4f}) "
            f"tail=({tail.x:.4f}, {tail.y:.4f}, {tail.z:.4f}) "
            f"parent={parent_name} connected={bone.use_connect}"
        )
        created[name] = bone

    calculate_bone_roll(armature)
    bpy.ops.object.mode_set(mode="OBJECT")
    armature.location = (0, 0, 0)
    armature.rotation_euler = (0, 0, 0)
    armature.scale = (1, 1, 1)
    log(f"Armature criada: {armature.name}, bones={len(armature.data.bones)}")
    return armature


def calculate_bone_roll(armature: bpy.types.Object) -> None:
    """Recalcula bone roll para reduzir eixos locais estranhos no FBX.

    GLOBAL_POS_Y costuma gerar orientação mais previsível para exportação FBX
    com axis_up='Y' na Unity. Se a versão do Blender não aceitar esse modo,
    usamos GLOBAL_POS_Z como fallback mantendo a posição dos bones.
    """

    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)

    try:
        bpy.ops.armature.select_all(action="SELECT")
        bpy.ops.armature.calculate_roll(type="GLOBAL_POS_Y")
        log("Bone roll recalculado com GLOBAL_POS_Y.")
    except Exception as exc:
        log(f"GLOBAL_POS_Y falhou ({exc}); tentando GLOBAL_POS_Z.")
        try:
            bpy.ops.armature.select_all(action="SELECT")
            bpy.ops.armature.calculate_roll(type="GLOBAL_POS_Z")
            log("Bone roll recalculado com GLOBAL_POS_Z.")
        except Exception as fallback_exc:
            log(f"Não foi possível recalcular bone roll: {fallback_exc}")


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
    log(f"Vinculando {len(mesh_objects)} mesh(es) à armature.")
    for obj in mesh_objects:
        matrix_world = obj.matrix_world.copy()
        obj.location = (0, 0, 0)
        obj.rotation_euler = (0, 0, 0)
        obj.scale = (1, 1, 1)
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
        log(f"  Mesh vinculado: {obj.name}, vertex_groups={len(groups)}")


def create_optional_test_pose(armature: bpy.types.Object) -> None:
    """Cria uma action de teste apenas quando MIXAMO_CREATE_TEST_POSE=1.

    A action fica desligada por padrão para não alterar o arquivo exportado.
    Ela serve como estrutura para debug futuro sem introduzir animação real na
    Fase 2.5.
    """

    if os.getenv("MIXAMO_CREATE_TEST_POSE") != "1":
        return

    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="POSE")
    action = bpy.data.actions.new("Rig_Test_Pose")
    armature.animation_data_create()
    armature.animation_data.action = action

    for frame in (1, 20):
        bpy.context.scene.frame_set(frame)
        for pose_bone in armature.pose.bones:
            pose_bone.rotation_mode = "XYZ"
            pose_bone.rotation_euler = (0, 0, 0)
            pose_bone.keyframe_insert(data_path="rotation_euler", frame=frame)

    bpy.context.scene.frame_set(10)
    for bone_name, rotation in {
        "LeftUpperArm": (0, 0, 0.35),
        "LeftLowerArm": (0, 0.25, 0),
    }.items():
        pose_bone = armature.pose.bones.get(bone_name)
        if pose_bone:
            pose_bone.rotation_mode = "XYZ"
            pose_bone.rotation_euler = rotation
            pose_bone.keyframe_insert(data_path="rotation_euler", frame=10)

    bpy.context.scene.frame_set(1)
    for pose_bone in armature.pose.bones:
        pose_bone.rotation_euler = (0, 0, 0)
    bpy.ops.object.mode_set(mode="OBJECT")
    log("Action opcional criada: Rig_Test_Pose.")


def export_scene(output_path: Path, export_format: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    log(f"Exportando arquivo {export_format.upper()}: {output_path}")

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
        log(f"Arquivo exportado: {output_path}")
        return

    try:
        bpy.ops.export_scene.fbx(
            filepath=str(output_path),
            use_selection=False,
            object_types={"ARMATURE", "MESH"},
            global_scale=1.0,
            apply_unit_scale=True,
            use_space_transform=True,
            axis_forward="-Z",
            axis_up="Y",
            add_leaf_bones=False,
            bake_anim=False,
            primary_bone_axis="Y",
            secondary_bone_axis="X",
            use_armature_deform_only=True,
        )
    except TypeError as exc:
        log(f"Export FBX com opções completas falhou ({exc}); usando fallback compatível.")
        bpy.ops.export_scene.fbx(
            filepath=str(output_path),
            use_selection=False,
            object_types={"ARMATURE", "MESH"},
            global_scale=1.0,
            axis_forward="-Z",
            axis_up="Y",
            add_leaf_bones=False,
            bake_anim=False,
        )
    log(f"Arquivo exportado: {output_path}")


def main() -> None:
    input_model_path, markers_json_path, output_path, export_format = read_args()

    clear_scene()
    import_model(input_model_path)
    normalize_scene_transforms()
    markers = load_markers(markers_json_path)
    bone_points, _ = build_bone_points(markers)
    armature = create_armature(bone_points)
    bind_meshes_to_armature(armature)
    create_optional_test_pose(armature)
    export_scene(output_path, export_format)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
