import * as THREE from "three";

export const REQUIRED_MARKERS = [
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
];

export const MARKER_LABELS_PT_BR = {
  chin: "Queixo",
  pelvis: "Pelve",
  leftShoulder: "Ombro esquerdo",
  rightShoulder: "Ombro direito",
  leftElbow: "Cotovelo esquerdo",
  rightElbow: "Cotovelo direito",
  leftWrist: "Punho esquerdo",
  rightWrist: "Punho direito",
  leftKnee: "Joelho esquerdo",
  rightKnee: "Joelho direito",
  leftAnkle: "Tornozelo esquerdo",
  rightAnkle: "Tornozelo direito",
};

export function getMarkerLabel(name) {
  return MARKER_LABELS_PT_BR[name] || name;
}

export class MarkerManager {
  constructor(sceneManager, options = {}) {
    this.sceneManager = sceneManager;
    this.onChange = options.onChange || (() => {});
    this.onWarning = options.onWarning || (() => {});
    this.activeMarker = REQUIRED_MARKERS[0];
    this.markers = new Map();
    this.listElement = null;
    this.pointerDown = null;

    this.sceneManager.renderer.domElement.addEventListener("pointerdown", (event) => {
      this.pointerDown = {
        x: event.clientX,
        y: event.clientY,
      };
    });

    this.sceneManager.renderer.domElement.addEventListener("pointerup", (event) => {
      this.handlePointerUp(event);
    });
  }

  mount(listElement) {
    this.listElement = listElement;
    this.renderList();
  }

  clear() {
    for (const marker of this.markers.values()) {
      this.sceneManager.markerGroup.remove(marker.mesh);
      marker.mesh.geometry.dispose();
      marker.mesh.material.dispose();
    }

    this.markers.clear();
    this.activeMarker = REQUIRED_MARKERS[0];
    this.renderList();
    this.onChange(this);
  }

  handlePointerUp(event) {
    if (!this.pointerDown) {
      return;
    }

    const moveDistance = Math.hypot(
      event.clientX - this.pointerDown.x,
      event.clientY - this.pointerDown.y,
    );
    this.pointerDown = null;

    if (moveDistance > 4) {
      return;
    }

    if (!this.activeMarker) {
      this.onWarning("Selecione um marcador antes de posicionar.");
      return;
    }

    const intersection = this.sceneManager.raycastModel(event);
    if (!intersection) {
      if (!this.sceneManager.modelRoot) {
        this.onWarning("Carregue um modelo 3D antes de posicionar marcadores.");
      }
      return;
    }

    this.placeMarker(this.activeMarker, intersection.point);
  }

  placeMarker(name, point) {
    const position = point.clone();
    const existing = this.markers.get(name);

    if (existing) {
      existing.mesh.position.copy(position);
      existing.position.copy(position);
    } else {
      const radius = this.sceneManager.getMarkerRadius();
      const geometry = new THREE.SphereGeometry(radius, 24, 16);
      const material = new THREE.MeshStandardMaterial({
        color: 0xe85d3f,
        emissive: 0x381208,
        roughness: 0.45,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.name = `marker_${name}`;
      mesh.position.copy(position);
      this.sceneManager.markerGroup.add(mesh);
      this.markers.set(name, { position, mesh });
    }

    this.renderList();
    this.onChange(this);
  }

  setActiveMarker(name) {
    if (!REQUIRED_MARKERS.includes(name)) {
      return;
    }

    this.activeMarker = name;
    this.renderList();
    this.onChange(this);
  }

  getMissingMarkers() {
    return REQUIRED_MARKERS.filter((name) => !this.markers.has(name));
  }

  getPlacedCount() {
    return this.markers.size;
  }

  toJSON() {
    const markers = {};

    for (const name of REQUIRED_MARKERS) {
      const marker = this.markers.get(name);
      if (!marker) {
        continue;
      }

      markers[name] = {
        x: Number(marker.position.x.toFixed(5)),
        y: Number(marker.position.y.toFixed(5)),
        z: Number(marker.position.z.toFixed(5)),
      };
    }

    return { markers };
  }

  renderList() {
    if (!this.listElement) {
      return;
    }

    this.listElement.replaceChildren();

    for (const name of REQUIRED_MARKERS) {
      const isPlaced = this.markers.has(name);
      const row = document.createElement("button");
      row.type = "button";
      row.className = "marker-row";
      row.dataset.marker = name;
      row.dataset.active = String(name === this.activeMarker);
      row.dataset.placed = String(isPlaced);

      const label = document.createElement("span");
      label.className = "marker-name";
      label.textContent = getMarkerLabel(name);

      const status = document.createElement("span");
      status.className = "marker-status";
      status.textContent = isPlaced ? "posicionado" : "pendente";

      row.append(label, status);
      row.addEventListener("click", () => this.setActiveMarker(name));
      this.listElement.appendChild(row);
    }
  }
}
