/**
 * Google Apps Script - シーンデータAPI
 *
 * デプロイ手順:
 * 1. Google Spreadsheetを開く
 * 2. 拡張機能 > Apps Script を選択
 * 3. このコードを貼り付け
 * 4. デプロイ > 新しいデプロイ を選択
 * 5. 種類: ウェブアプリ
 * 6. 次のユーザーとして実行: 自分
 * 7. アクセスできるユーザー: 全員
 * 8. デプロイ後のURLを.envに設定
 */

// スプレッドシートID (URLから取得: docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit)
const SPREADSHEET_ID = "1bzROAf4BHIdq551QpWbRL1xRnB2hFqJGQ9Mu9Vj0w-c";

// シート名
const SCENE_SHEET_NAME = "scenes";
const IMAGE_SHEET_NAME = "images";

/**
 * メインハンドラー - GET/POSTリクエストを処理
 */
function doGet(e) {
  const action = e.parameter.action;

  try {
    if (action === "getScenes") {
      return getScenesData();
    }

    return ContentService.createTextOutput(
      JSON.stringify({ error: "Invalid action" })
    ).setMimeType(ContentService.MimeType.JSON);
  } catch (error) {
    return ContentService.createTextOutput(
      JSON.stringify({ error: error.message })
    ).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * シーンデータと画像データを取得
 */
function getScenesData() {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);

  // シーン情報を取得
  const sceneSheet = ss.getSheetByName(SCENE_SHEET_NAME);
  const sceneData = sceneSheet.getDataRange().getValues();
  const scenes = [];

  for (let i = 1; i < sceneData.length; i++) {
    const row = sceneData[i];
    if (row[0] != "") {
      // IDが空でない行のみ
      scenes.push({
        title: row[0],
        content: row[1],
        telop: row[2],
        processIndex: row[6],
      });
    }
  }

  // 画像データを取得
  const imageSheet = ss.getSheetByName(IMAGE_SHEET_NAME);
  const imageData = imageSheet.getDataRange().getValues();
  const images = {};

  for (let i = 1; i < imageData.length; i++) {
    const row = imageData[i];
    const processIndex = row[0];
    const imageUrl = row[4];

    if (!images[processIndex]) {
      images[processIndex] = [];
    }
    images[processIndex].push(imageUrl);
  }

  const result = {
    scenes: scenes,
    images: images,
  };

  return ContentService.createTextOutput(JSON.stringify(result)).setMimeType(
    ContentService.MimeType.JSON
  );
}

/**
 * テスト用関数 - Apps Scriptエディタで実行して動作確認
 */
function testGetScenes() {
  const result = getScenesData();
  Logger.log(result.getContent());
}
