import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

export class SceneManager {
  constructor(container) {
    this.container = container;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xf4f2ed);

    this.camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000);
    this.camera.position.set(2.5, 1.8, 2.5);

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.target.set(0, 0.8, 0);

    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.modelRoot = null;
    this.clickTargets = [];
    this.modelSize = 1;
    this.lastCameraState = null;
    this.clock = new THREE.Clock();
    this.updateCallbacks = new Set();

    this.markerGroup = new THREE.Group();
    this.markerGroup.name = "AnatomicalMarkers";
    this.scene.add(this.markerGroup);

    this.addLights();
    this.addGrid();
    this.handleResize();

    this.resizeObserver = new ResizeObserver(() => this.handleResize());
    this.resizeObserver.observe(container);

    this.animate();
  }

  addLights() {
    const ambientLight = new THREE.HemisphereLight(0xffffff, 0x626262, 1.8);
    this.scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xffffff, 2.5);
    keyLight.position.set(3, 5, 4);
    this.scene.add(keyLight);
  }

  addGrid() {
    const grid = new THREE.GridHelper(4, 40, 0x7f8c8d, 0xd0d3d4);
    grid.name = "GroundGrid";
    this.scene.add(grid);
  }

  setModel(model) {
    if (this.modelRoot) {
      this.scene.remove(this.modelRoot);
      this.disposeObject(this.modelRoot);
    }

    this.modelRoot = model;
    this.scene.add(model);
    this.centerModel(model);
    this.collectClickTargets(model);
    this.fitCameraToObject(model);
  }

  centerModel(model) {
    model.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(model);

    if (box.isEmpty()) {
      return;
    }

    const center = box.getCenter(new THREE.Vector3());
    model.position.sub(center);
    model.updateMatrixWorld(true);
  }

  collectClickTargets(model) {
    this.clickTargets = [];
    model.traverse((object) => {
      if (object.isMesh) {
        object.geometry.computeBoundingSphere();
        this.clickTargets.push(object);
      }
    });
  }

  fitCameraToObject(object) {
    object.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(object);

    if (box.isEmpty()) {
      return;
    }

    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxSize = Math.max(size.x, size.y, size.z, 1);
    const fov = THREE.MathUtils.degToRad(this.camera.fov);
    const distance = (maxSize / (2 * Math.tan(fov / 2))) * 1.45;
    const direction = new THREE.Vector3(1, 0.65, 1).normalize();

    this.modelSize = maxSize;
    this.camera.near = Math.max(distance / 100, 0.001);
    this.camera.far = distance * 100;
    this.camera.position.copy(center).add(direction.multiplyScalar(distance));
    this.camera.updateProjectionMatrix();

    this.controls.target.copy(center);
    this.controls.maxDistance = distance * 8;
    this.controls.update();

    this.lastCameraState = {
      position: this.camera.position.clone(),
      target: this.controls.target.clone(),
      near: this.camera.near,
      far: this.camera.far,
    };
  }

  resetCamera() {
    if (!this.lastCameraState) {
      this.camera.position.set(2.5, 1.8, 2.5);
      this.controls.target.set(0, 0.8, 0);
      this.controls.update();
      return;
    }

    this.camera.position.copy(this.lastCameraState.position);
    this.camera.near = this.lastCameraState.near;
    this.camera.far = this.lastCameraState.far;
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(this.lastCameraState.target);
    this.controls.update();
  }

  raycastModel(event) {
    if (!this.clickTargets.length) {
      return null;
    }

    const rect = this.renderer.domElement.getBoundingClientRect();
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.pointer, this.camera);
    const intersections = this.raycaster.intersectObjects(this.clickTargets, true);
    return intersections[0] || null;
  }

  getMarkerRadius() {
    return Math.max(this.modelSize * 0.018, 0.015);
  }

  handleResize() {
    const width = Math.max(this.container.clientWidth, 1);
    const height = Math.max(this.container.clientHeight, 1);

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    const delta = this.clock.getDelta();
    for (const callback of this.updateCallbacks) {
      callback(delta);
    }
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  addUpdateCallback(callback) {
    this.updateCallbacks.add(callback);
    return () => this.updateCallbacks.delete(callback);
  }

  disposeObject(object) {
    object.traverse((child) => {
      if (child.geometry) {
        child.geometry.dispose();
      }

      if (child.material) {
        const materials = Array.isArray(child.material) ? child.material : [child.material];
        materials.forEach((material) => material.dispose());
      }
    });
  }
}
