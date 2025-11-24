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
const SELECTION_SHEET_NAME = "selections";

/**
 * メインハンドラー - GET/POSTリクエストを処理
 */
function doGet(e) {
  const action = e.parameter.action;

  try {
    if (action === "getScenes") {
      return getScenesData();
    } else if (action === "submitSelections") {
      const selections = JSON.parse(e.parameter.data);
      return submitSelections(selections);
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

function submitSelections(selections) {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);

  // 結果シートを取得または作成
  let resultSheet = ss.getSheetByName(SELECTION_SHEET_NAME);
  if (!resultSheet) {
    resultSheet = ss.insertSheet(SELECTION_SHEET_NAME);
  } else {
    // 既存のシートをクリア
    resultSheet.clear();
  }

  if (selections.length === 0) {
    return ContentService.createTextOutput(
      JSON.stringify({
        success: false,
        message: "データが空です",
      })
    ).setMimeType(ContentService.MimeType.JSON);
  }

  // ヘッダー行を作成（最初のレコードのキーから）
  const headers = Object.keys(selections[0]);
  resultSheet.appendRow(headers);

  // データ行を追加
  selections.forEach(function (record) {
    const row = headers.map(function (header) {
      return record[header];
    });
    resultSheet.appendRow(row);
  });

  return ContentService.createTextOutput(
    JSON.stringify({
      success: true,
      message: "選択内容を保存しました",
      count: selections.length,
    })
  ).setMimeType(ContentService.MimeType.JSON);
}

/**
 * テスト用関数 - Apps Scriptエディタで実行して動作確認
 */
function testGetScenes() {
  const result = getScenesData();
  Logger.log(result.getContent());
}
