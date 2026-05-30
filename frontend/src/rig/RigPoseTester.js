import * as THREE from "three";

import { findAllBones, findBoneByName, findSkinnedMeshes, updateSkeletons } from "./BoneUtils.js";

const TEST_POSES = {
  leftArm: {
    boneName: "LeftUpperArm",
    rotation: { z: 0.7 },
  },
  rightArm: {
    boneName: "RightUpperArm",
    rotation: { z: -0.7 },
  },
  leftElbow: {
    boneName: "LeftLowerArm",
    rotation: { y: 0.75 },
  },
  rightElbow: {
    boneName: "RightLowerArm",
    rotation: { y: -0.75 },
  },
  leftLeg: {
    boneName: "LeftUpperLeg",
    rotation: { x: -0.55 },
  },
  rightLeg: {
    boneName: "RightUpperLeg",
    rotation: { x: -0.55 },
  },
  leftKnee: {
    boneName: "LeftLowerLeg",
    rotation: { x: 0.75 },
  },
  rightKnee: {
    boneName: "RightLowerLeg",
    rotation: { x: 0.75 },
  },
  head: {
    boneName: "Head",
    rotation: { y: 0.3, z: 0.15 },
  },
};

export class RigPoseTester {
  constructor(sceneManager, options = {}) {
    this.sceneManager = sceneManager;
    this.onWarning = options.onWarning || (() => {});
    this.root = null;
    this.animations = [];
    this.bindPose = new Map();
    this.mixer = null;
    this.activeAction = null;

    this.sceneManager.addUpdateCallback((delta) => this.update(delta));
  }

  setRig(gltf) {
    this.clear();
    this.root = gltf?.scene || null;
    this.animations = gltf?.animations || [];
    this.mixer = this.root ? new THREE.AnimationMixer(this.root) : null;
    this.storeBindPose();

    const bones = findAllBones(this.root);
    const skinnedMeshes = findSkinnedMeshes(this.root);
    const warnings = [];

    if (bones.length === 0 || skinnedMeshes.length === 0) {
      warnings.push(
        "Não foi possível acessar skeleton/bones no preview GLB. Teste o FBX no Blender/Unity.",
      );
    }

    for (const warning of warnings) {
      this.onWarning(warning);
    }

    return warnings;
  }

  clear() {
    this.stopAction();
    this.root = null;
    this.animations = [];
    this.bindPose.clear();
    this.mixer = null;
  }

  hasRig() {
    return Boolean(this.root && findAllBones(this.root).length > 0);
  }

  hasAction(actionName) {
    return this.animations.some((clip) => clip.name === actionName);
  }

  storeBindPose() {
    this.bindPose.clear();
    for (const bone of findAllBones(this.root)) {
      this.bindPose.set(bone.uuid, {
        bone,
        position: bone.position.clone(),
        quaternion: bone.quaternion.clone(),
        scale: bone.scale.clone(),
      });
    }
  }

  resetPose() {
    this.stopAction();
    for (const snapshot of this.bindPose.values()) {
      snapshot.bone.position.copy(snapshot.position);
      snapshot.bone.quaternion.copy(snapshot.quaternion);
      snapshot.bone.scale.copy(snapshot.scale);
      snapshot.bone.updateMatrixWorld(true);
    }
    updateSkeletons(this.root);
  }

  applyTestPose(poseName) {
    const pose = TEST_POSES[poseName];
    if (!pose) {
      return;
    }

    if (!this.hasRig()) {
      this.onWarning(
        "Não foi possível acessar skeleton/bones no preview GLB. Teste o FBX no Blender/Unity.",
      );
      return;
    }

    this.stopAction();
    this.resetPose();

    const bone = findBoneByName(this.root, pose.boneName);
    if (!bone) {
      this.onWarning(`Bone ${pose.boneName} não encontrado no modelo carregado.`);
      return;
    }

    bone.rotation.x += pose.rotation.x || 0;
    bone.rotation.y += pose.rotation.y || 0;
    bone.rotation.z += pose.rotation.z || 0;
    bone.updateMatrixWorld(true);
    updateSkeletons(this.root);
  }

  toggleAction(actionName) {
    if (!this.mixer || !this.root) {
      this.onWarning(
        "Não foi possível acessar skeleton/bones no preview GLB. Teste o FBX no Blender/Unity.",
      );
      return false;
    }

    if (this.activeAction) {
      this.stopAction();
      this.resetPose();
      return false;
    }

    const clip = this.animations.find((animation) => animation.name === actionName);
    if (!clip) {
      this.onWarning(`Action ${actionName} não encontrada no GLB de preview.`);
      return false;
    }

    this.resetPose();
    this.activeAction = this.mixer.clipAction(clip);
    this.activeAction.reset();
    this.activeAction.setLoop(THREE.LoopRepeat, Infinity);
    this.activeAction.play();
    return true;
  }

  stopAction() {
    if (this.activeAction) {
      this.activeAction.stop();
      this.activeAction = null;
    }

    if (this.mixer) {
      this.mixer.stopAllAction();
    }
  }

  update(delta) {
    if (this.mixer && this.activeAction) {
      this.mixer.update(delta);
      updateSkeletons(this.root);
    }
  }
}
