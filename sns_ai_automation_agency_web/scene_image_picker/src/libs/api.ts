import { ScenesData } from "../types/scene";
import { SelectedImage } from "../types/submit";

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

    // data.images = data.images.slice(0, 1);
    // data.scenes = data.scenes.slice(0, 1);
    return data;
  } catch (error) {
    console.error("Failed to fetch scenes data:", error);
    throw error;
  }
}

/**
 * 選択内容をGASに送信してスプレッドシートに書き込む
 */
export async function submitSelections(
  selections: SelectedImage[]
): Promise<{ success: boolean; message?: string; count?: number }> {
  // 空配列チェック
  if (selections.length === 0) {
    throw new Error("送信するデータがありません");
  }

  try {
    // POSTではなくGETパラメータとして送信（CORS回避）
    const params = new URLSearchParams({
      action: "submitSelections",
      data: JSON.stringify(selections),
    });

    const response = await fetch(`${GAS_API_URL}?${params.toString()}`, {
      method: "GET",
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const contentType = response.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
      throw new Error("Invalid response format");
    }

    const data = await response.json();

    // GAS側のエラーをチェック
    if (data.error) {
      throw new Error(data.error);
    }

    return data;
  } catch (error) {
    console.error("Failed to submit selections:", error);
    throw error;
  }
}
