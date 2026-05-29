import "./styles.css";

import { convertModel, generateRig, resolveModelUrl } from "./api/client.js";
import { getMarkerLabel, MarkerManager, REQUIRED_MARKERS } from "./markers/MarkerManager.js";
import { ModelLoader } from "./viewer/ModelLoader.js";
import { SceneManager } from "./viewer/SceneManager.js";

const uploadForm = document.querySelector("#uploadForm");
const fileInput = document.querySelector("#modelFileInput");
const uploadButton = document.querySelector("#uploadButton");
const selectedFileName = document.querySelector("#selectedFileName");
const resetCameraButton = document.querySelector("#resetCameraButton");
const exportMarkersButton = document.querySelector("#exportMarkersButton");
const generateRigButton = document.querySelector("#generateRigButton");
const rigFormatSelect = document.querySelector("#rigFormatSelect");
const downloadRigLink = document.querySelector("#downloadRigLink");
const statusMessage = document.querySelector("#statusMessage");
const viewer = document.querySelector("#viewer");
const markerList = document.querySelector("#markerList");
const markerCount = document.querySelector("#markerCount");
const allowedExtensions = [".obj", ".fbx", ".glb", ".gltf"];
let currentModelFilename = null;
let isUploading = false;
let isRigging = false;

const sceneManager = new SceneManager(viewer);
const modelLoader = new ModelLoader(sceneManager);
const markerManager = new MarkerManager(sceneManager, {
  onChange: updateMarkerState,
  onWarning: (message) => showStatus(message, "warning"),
});

markerManager.mount(markerList);
updateMarkerState();

fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  selectedFileName.textContent = file ? file.name : "Nenhum arquivo selecionado";
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = fileInput.files?.[0];
  if (!file) {
    showStatus("Selecione um arquivo 3D para converter.", "warning");
    return;
  }

  if (!isAllowedFile(file.name)) {
    showStatus("Formato inválido. Use .obj, .fbx, .glb ou .gltf.", "error");
    return;
  }

  setUploadState(true);
  currentModelFilename = null;
  resetRigDownload();
  showStatus("Convertendo modelo com Blender...", "info");

  try {
    const response = await convertModel(file);
    const modelUrl = resolveModelUrl(response.fileUrl || response.downloadUrl);
    await modelLoader.loadFromUrl(modelUrl);
    currentModelFilename = response.processedFilename;
    markerManager.clear();
    showStatus(`Modelo carregado: ${response.originalFilename}`, "success");
  } catch (error) {
    showStatus(error.message, "error");
  } finally {
    setUploadState(false);
  }
});

resetCameraButton.addEventListener("click", () => {
  sceneManager.resetCamera();
});

exportMarkersButton.addEventListener("click", () => {
  const missingMarkers = markerManager.getMissingMarkers();

  if (missingMarkers.length > 0) {
    const missingLabels = missingMarkers.map((name) => getMarkerLabel(name));
    showStatus(`Marcadores pendentes: ${missingLabels.join(", ")}`, "warning");
    return;
  }

  const payload = JSON.stringify(markerManager.toJSON(), null, 2);
  const blob = new Blob([payload], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "markers.json";
  anchor.click();
  URL.revokeObjectURL(url);
  showStatus("Arquivo markers.json gerado.", "success");
});

generateRigButton.addEventListener("click", async () => {
  if (!currentModelFilename) {
    showStatus("Carregue um modelo convertido antes de gerar o rig.", "warning");
    return;
  }

  const missingMarkers = markerManager.getMissingMarkers();
  if (missingMarkers.length > 0) {
    const missingLabels = missingMarkers.map((name) => getMarkerLabel(name));
    showStatus(`Marcadores pendentes: ${missingLabels.join(", ")}`, "warning");
    return;
  }

  setRigState(true);
  resetRigDownload();
  showStatus("Gerando armature no Blender...", "info");

  try {
    const exportFormat = rigFormatSelect.value;
    const response = await generateRig({
      modelFilename: currentModelFilename,
      markers: markerManager.toJSON().markers,
      exportFormat,
    });

    const previewUrl = response.previewUrl || (response.exportFormat === "glb" ? response.fileUrl : null);
    if (previewUrl) {
      await modelLoader.loadFromUrl(resolveModelUrl(previewUrl));
    }

    updateRigDownload(response);
    triggerRigDownload(response);

    if (response.exportFormat === "fbx") {
      showStatus(
        "FBX gerado para teste na Unity/Blender. Download iniciado e GLB de preview carregado.",
        "success",
      );
    } else {
      showStatus("GLB rigado gerado, carregado para preview e download iniciado.", "success");
    }
  } catch (error) {
    showStatus(error.message, "error");
  } finally {
    setRigState(false);
  }
});

function isAllowedFile(filename) {
  const lowerName = filename.toLowerCase();
  return allowedExtensions.some((extension) => lowerName.endsWith(extension));
}

function setUploadState(nextIsUploading) {
  isUploading = nextIsUploading;
  uploadButton.disabled = isUploading;
  fileInput.disabled = isUploading;
  uploadButton.textContent = isUploading ? "Convertendo..." : "Converter e carregar";
  updateRigButtonState();
}

function setRigState(nextIsRigging) {
  isRigging = nextIsRigging;
  generateRigButton.textContent = isRigging ? "Gerando..." : "Gerar Rig";
  updateRigButtonState();
}

function updateRigDownload(response) {
  downloadRigLink.href = resolveModelUrl(response.fileUrl);
  downloadRigLink.download = response.riggedFilename;
  downloadRigLink.textContent = `Baixar rig ${response.exportFormat.toUpperCase()}`;
  downloadRigLink.hidden = false;
}

function triggerRigDownload(response) {
  const anchor = document.createElement("a");
  anchor.href = resolveModelUrl(response.fileUrl);
  anchor.download = response.riggedFilename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

function resetRigDownload() {
  downloadRigLink.removeAttribute("href");
  downloadRigLink.removeAttribute("download");
  downloadRigLink.hidden = true;
}

function updateRigButtonState() {
  const allMarkersPlaced = markerManager.getMissingMarkers().length === 0;
  generateRigButton.disabled = isUploading || isRigging || !currentModelFilename || !allMarkersPlaced;
  rigFormatSelect.disabled = isUploading || isRigging;
}

function showStatus(message, type = "info") {
  statusMessage.textContent = message;
  statusMessage.dataset.type = type;
}

function updateMarkerState() {
  markerCount.textContent = `${markerManager.getPlacedCount()}/${REQUIRED_MARKERS.length}`;
  updateRigButtonState();
}
