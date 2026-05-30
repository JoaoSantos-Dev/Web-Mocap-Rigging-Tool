import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

export class ModelLoader {
  constructor(sceneManager) {
    this.sceneManager = sceneManager;
    this.loader = new GLTFLoader();
  }

  loadFromUrl(url) {
    return new Promise((resolve, reject) => {
      this.loader.load(
        url,
        (gltf) => {
          this.sceneManager.setModel(gltf.scene);
          resolve(gltf);
        },
        undefined,
        (error) => {
          reject(new Error("Não foi possível carregar o modelo convertido na cena 3D."));
        },
      );
    });
  }
}
