export interface Scene {
  processIndex: number;
  title: string;
  telop: string;
  content: string;
}

export interface SceneImages {
  [sceneId: number]: string[];
}

export interface ScenesData {
  scenes: Scene[];
  images: SceneImages;
}
