import { useState, useEffect } from "react";
import { Check, X, Save, Loader2 } from "lucide-react";
import { SceneSelector } from "./components/SceneSelector";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "./components/ui/accordion";
import { Button } from "./components/ui/button";
import { Card } from "./components/ui/card";
import { ImageWithFallback } from "./components/figma/ImageWithFallback";
import { fetchScenesData } from "./lib/api";
import type { Scene, SceneImages } from "./types/scene";

export default function App() {
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [sceneImages, setSceneImages] = useState<SceneImages>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selections, setSelections] = useState<Record<number, number>>({});
  const [showSummary, setShowSummary] = useState(false);

  // GASからデータを取得
  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const data = await fetchScenesData();
        setScenes(data.scenes);
        setSceneImages(data.images);
        setError(null);
      } catch (err) {
        console.error("Failed to load scenes:", err);
        setError(
          "データの取得に失敗しました。しばらく経ってから再度お試しください。"
        );
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const handleSelectImage = (sceneId: number, imageIndex: number) => {
    setSelections((prev: Record<number, number>) => ({
      ...prev,
      [sceneId]: imageIndex,
    }));
  };

  const handleClearSelection = (sceneId: number) => {
    setSelections((prev: Record<number, number>) => {
      const newSelections = { ...prev };
      delete newSelections[sceneId];
      return newSelections;
    });
  };

  const handleClearAll = () => {
    setSelections({});
    setShowSummary(false);
  };

  const handleSubmit = () => {
    setShowSummary(true);
  };

  const selectedCount = Object.keys(selections).length;
  const allSelected = selectedCount === scenes.length;

  // ローディング表示
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center space-y-4">
          <Loader2 className="size-12 animate-spin mx-auto text-blue-500" />
          <p className="text-gray-600">データを読み込んでいます...</p>
        </div>
      </div>
    );
  }

  // エラー表示
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="p-8 max-w-md">
          <div className="text-center space-y-4">
            <div className="text-red-500 text-5xl">⚠️</div>
            <h2 className="text-xl">エラーが発生しました</h2>
            <p className="text-gray-600">{error}</p>
            <Button onClick={() => window.location.reload()}>再読み込み</Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="mb-2">SNS投稿画像選択システム</h1>
          <p className="text-gray-600">
            各シーンの候補画像から、SNS投稿に最適な画像を選択してください。
          </p>
        </div>

        {/* 進捗状況 */}
        <Card className="mb-6 p-4">
          <div className="flex items-center justify-between mb-2">
            <div>
              <span className="mr-2">選択進捗:</span>
              <span className={allSelected ? "text-green-600" : ""}>
                {selectedCount} / {scenes.length} シーン
              </span>
            </div>
            <div className="flex gap-2">
              {selectedCount > 0 && (
                <Button variant="outline" size="sm" onClick={handleClearAll}>
                  <X className="size-4 mr-1" />
                  すべてクリア
                </Button>
              )}
              <Button
                onClick={handleSubmit}
                disabled={selectedCount === 0}
                size="sm"
              >
                <Save className="size-4 mr-1" />
                選択を確定
              </Button>
            </div>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2 mb-4">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all"
              style={{
                width: `${(selectedCount / scenes.length) * 100}%`,
              }}
            />
          </div>

          {/* 選択中の画像プレビュー */}
          {selectedCount > 0 && (
            <div className="mt-4 pt-4 border-t">
              <h3 className="text-sm mb-3">選択中の画像</h3>
              <div className="flex gap-3 overflow-x-auto pb-2">
                {scenes
                  .filter(
                    (scene: Scene) =>
                      selections[scene.processIndex] !== undefined
                  )
                  .map((scene: Scene) => {
                    const imageIndex = selections[scene.processIndex];
                    const imageUrl =
                      sceneImages[scene.processIndex]?.[imageIndex] || "";
                    return (
                      <div
                        key={scene.processIndex}
                        className="flex-shrink-0 w-32 space-y-1"
                      >
                        <div className="aspect-square rounded-md overflow-hidden border-2 border-blue-500 relative group">
                          <ImageWithFallback
                            src={imageUrl}
                            alt={scene.title}
                            className="w-full h-full object-cover"
                          />
                          <button
                            onClick={() =>
                              handleClearSelection(scene.processIndex)
                            }
                            className="absolute top-1 right-1 bg-red-500 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            <X className="size-3" />
                          </button>
                        </div>
                        <p className="text-xs text-center text-gray-600 truncate">
                          {scene.title}
                        </p>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}
        </Card>

        {/* 選択サマリー */}
        {showSummary && selectedCount > 0 && (
          <Card className="mb-6 p-6 bg-green-50 border-green-200">
            <h2 className="mb-4 flex items-center gap-2">
              <Check className="size-6 text-green-600" />
              選択完了
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {scenes
                .filter(
                  (scene: Scene) => selections[scene.processIndex] !== undefined
                )
                .map((scene: Scene) => {
                  const imageIndex = selections[scene.processIndex];
                  const imageUrl =
                    sceneImages[scene.processIndex]?.[imageIndex] || "";
                  return (
                    <div key={scene.processIndex} className="space-y-2">
                      <div className="aspect-square rounded-lg overflow-hidden border-2 border-green-500">
                        <ImageWithFallback
                          src={imageUrl}
                          alt={scene.title}
                          className="w-full h-full object-cover"
                        />
                      </div>
                      <p className="text-sm text-center">{scene.title}</p>
                    </div>
                  );
                })}
            </div>
          </Card>
        )}

        {/* シーン選択 */}
        <Accordion type="multiple" className="space-y-4">
          {scenes.map((scene: Scene) => {
            const images = sceneImages[scene.processIndex] || [];
            const selectedImage = selections[scene.processIndex] ?? null;
            console.log(scene);
            console.log(scene.processIndex);
            console.log(sceneImages);
            console.log(images);

            return (
              <AccordionItem
                key={scene.processIndex}
                value={`scene-${scene.processIndex}`}
                className="bg-white rounded-lg border px-6"
              >
                <AccordionTrigger className="hover:no-underline">
                  <div className="flex items-start gap-3 w-full py-2">
                    <div
                      className={`flex items-center justify-center size-8 rounded-full flex-shrink-0 mt-1 ${
                        selectedImage !== null
                          ? "bg-green-500 text-white"
                          : "bg-gray-200 text-gray-600"
                      }`}
                    >
                      {selectedImage !== null ? (
                        <Check className="size-5" />
                      ) : (
                        <span>{scene.processIndex}</span>
                      )}
                    </div>
                    <div className="flex-1 text-left space-y-1 min-w-0">
                      <div>{scene.title}</div>
                      <div className="text-sm text-blue-600">{scene.telop}</div>
                      <p className="text-sm text-gray-600 pr-8">
                        {scene.content}
                      </p>
                    </div>
                    {selectedImage !== null && (
                      <div
                        onClick={(e) => {
                          e.stopPropagation();
                          handleClearSelection(scene.processIndex);
                        }}
                        className="flex items-center justify-center size-8 rounded-md text-gray-500 hover:text-red-600 hover:bg-gray-100 flex-shrink-0 cursor-pointer transition-colors"
                      >
                        <X className="size-4" />
                      </div>
                    )}
                  </div>
                </AccordionTrigger>
                <AccordionContent className="pt-4 pb-6">
                  <SceneSelector
                    sceneId={scene.processIndex}
                    sceneName={scene.title}
                    images={images}
                    selectedImage={selectedImage}
                    onSelectImage={(imageIndex) =>
                      handleSelectImage(scene.processIndex, imageIndex)
                    }
                  />
                </AccordionContent>
              </AccordionItem>
            );
          })}
        </Accordion>

        {/* フッター */}
        <div className="mt-8 text-center text-gray-500 text-sm">
          <p>
            各シーンから1つの画像を選択し、「選択を確定」ボタンをクリックしてください。
          </p>
        </div>
      </div>
    </div>
  );
}
