export const HUMANOID_BONE_NAMES = [
  "Hips",
  "Spine",
  "Chest",
  "Neck",
  "Head",
  "LeftUpperArm",
  "LeftLowerArm",
  "LeftHand",
  "RightUpperArm",
  "RightLowerArm",
  "RightHand",
  "LeftUpperLeg",
  "LeftLowerLeg",
  "LeftFoot",
  "RightUpperLeg",
  "RightLowerLeg",
  "RightFoot",
];

export function findBoneByName(root, boneName) {
  if (!root) {
    return null;
  }

  let found = null;
  root.traverse((object) => {
    if (!found && object.name === boneName && (object.isBone || object.type === "Bone")) {
      found = object;
    }
  });

  if (!found) {
    for (const mesh of findSkinnedMeshes(root)) {
      found = mesh.skeleton?.bones.find((bone) => bone.name === boneName) || null;
      if (found) {
        break;
      }
    }
  }

  return found;
}

export function findAllBones(root) {
  const bones = [];
  const boneIds = new Set();
  if (!root) {
    return bones;
  }

  const addBone = (bone) => {
    if (!boneIds.has(bone.uuid)) {
      bones.push(bone);
      boneIds.add(bone.uuid);
    }
  };

  root.traverse((object) => {
    if (object.isBone || object.type === "Bone") {
      addBone(object);
    }
  });

  for (const mesh of findSkinnedMeshes(root)) {
    for (const bone of mesh.skeleton?.bones || []) {
      addBone(bone);
    }
  }

  return bones;
}

export function findSkinnedMeshes(root) {
  const meshes = [];
  if (!root) {
    return meshes;
  }

  root.traverse((object) => {
    if (object.isSkinnedMesh) {
      meshes.push(object);
    }
  });

  return meshes;
}

export function updateSkeletons(root) {
  for (const mesh of findSkinnedMeshes(root)) {
    mesh.skeleton?.update();
  }
}
