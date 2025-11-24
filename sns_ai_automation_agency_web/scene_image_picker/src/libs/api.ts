import { ScenesData } from "../types/scene";

const GAS_API_URL = import.meta.env.VITE_GAS_API_URL;

/**
 * GASからシーン一覧と画像データを取得
 * 環境変数が未設定の場合はモックデータを返す
 */
export async function fetchScenesData(): Promise<ScenesData> {
  try {
    const response = await fetch(`${GAS_API_URL}?action=getScenes`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const contentType = response.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
      throw new Error("Response is not JSON. Check if GAS URL is correct.");
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Failed to fetch scenes data:", error);
    throw error;
  }
}
