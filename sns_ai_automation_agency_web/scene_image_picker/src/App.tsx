import { useState } from "react";
import { Check, X, Save } from "lucide-react";
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

// シーンの定義
const SCENES = [
  {
    id: 1,
    name: "ビジネスミーティング",
    telop: "重要な戦略会議",
    description:
      "チームメンバーと共に新しいプロジェクトの方向性を決定する重要な会議の様子を伝えます。",
  },
  {
    id: 2,
    name: "オフィスワークスペース",
    telop: "快適な作業環境",
    description:
      "生産性を高める理想的なオフィス環境で、集中して業務に取り組む様子を表現します。",
  },
  {
    id: 3,
    name: "チームコラボレーション",
    telop: "みんなで創る未来",
    description:
      "チーム全員が一丸となってアイデアを出し合い、革新的なソリューションを生み出す瞬間です。",
  },
  {
    id: 4,
    name: "コーヒーブレイク",
    telop: "リフレッシュの時間",
    description:
      "仕事の合間の貴重な休憩時間。リラックスして次のタスクへのエネルギーをチャージします。",
  },
  {
    id: 5,
    name: "製品ローンチ",
    telop: "新商品がついに登場",
    description:
      "長期間の開発を経て、ついに新製品をお披露目する記念すべき瞬間を共有します。",
  },
  {
    id: 6,
    name: "企業イベント",
    telop: "全社員が一堂に集結",
    description:
      "年に一度の社員総会やパーティーで、組織の団結力と企業文化の素晴らしさを伝えます。",
  },
  {
    id: 7,
    name: "テクノロジーイノベーション",
    telop: "最先端技術の活用",
    description:
      "AI、IoT、クラウドなど最新テクノロジーを駆使して、ビジネスの可能性を広げる取り組みを紹介します。",
  },
  {
    id: 8,
    name: "カスタマーサービス",
    telop: "お客様第一の精神",
    description:
      "顧客一人ひとりに寄り添った丁寧なサポートで、信頼関係を築く私たちのサービス姿勢を表します。",
  },
  {
    id: 9,
    name: "リモートワーク",
    telop: "どこでも働ける自由",
    description:
      "場所にとらわれない柔軟な働き方で、ワークライフバランスと生産性の両立を実現しています。",
  },
  {
    id: 10,
    name: "ビジネス成功",
    telop: "目標達成の瞬間",
    description:
      "チーム全員の努力が実り、売上目標を達成した喜びと達成感を分かち合う感動的な場面です。",
  },
  {
    id: 11,
    name: "プレゼンテーション",
    telop: "説得力のある提案",
    description:
      "クライアントに向けて、データと情熱を込めたプレゼンテーションで価値を伝える姿勢を示します。",
  },
  {
    id: 12,
    name: "ネットワーキング",
    telop: "新たな繋がりの創出",
    description:
      "業界イベントやセミナーでの出会いを通じて、ビジネスネットワークを広げる積極的な姿勢を表現します。",
  },
];

// 各シーン用の画像データ（実際のアプリケーションではAPIから取得）
const generateSceneImages = (sceneId: number): string[] => {
  const baseImages = [
    "https://images.unsplash.com/photo-1709715357520-5e1047a2b691?w=400",
    "https://images.unsplash.com/photo-1462826303086-329426d1aef5?w=400",
    "https://images.unsplash.com/photo-1600880292089-90a7e086ee0c?w=400",
    "https://images.unsplash.com/photo-1604992713105-46604174ab0a?w=400",
    "https://images.unsplash.com/photo-1505373877841-8d25f7d46678?w=400",
    "https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=400",
    "https://images.unsplash.com/photo-1568952433726-3896e3881c65?w=400",
    "https://images.unsplash.com/photo-1553775282-20af80779df7?w=400",
    "https://images.unsplash.com/photo-1586227740560-8cf2732c1531?w=400",
    "https://images.unsplash.com/photo-1600880292203-757bb62b4baf?w=400",
  ];

  // シーンごとに異なる順序で画像を返す（デモ用）
  const offset = (sceneId * 3) % baseImages.length;
  return baseImages.map((url, index) => {
    const newIndex = (index + offset) % baseImages.length;
    return baseImages[newIndex];
  });
};

export default function App() {
  const [selections, setSelections] = useState<
    Record<number, number>
  >({});
  const [showSummary, setShowSummary] = useState(false);

  const handleSelectImage = (
    sceneId: number,
    imageIndex: number,
  ) => {
    setSelections((prev) => ({
      ...prev,
      [sceneId]: imageIndex,
    }));
  };

  const handleClearSelection = (sceneId: number) => {
    setSelections((prev) => {
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
  const allSelected = selectedCount === SCENES.length;

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
              <span
                className={allSelected ? "text-green-600" : ""}
              >
                {selectedCount} / {SCENES.length} シーン
              </span>
            </div>
            <div className="flex gap-2">
              {selectedCount > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleClearAll}
                >
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
                width: `${(selectedCount / SCENES.length) * 100}%`,
              }}
            />
          </div>

          {/* 選択中の画像プレビュー */}
          {selectedCount > 0 && (
            <div className="mt-4 pt-4 border-t">
              <h3 className="text-sm mb-3">選択中の画像</h3>
              <div className="flex gap-3 overflow-x-auto pb-2">
                {SCENES.filter(
                  (scene) => selections[scene.id] !== undefined,
                ).map((scene) => {
                  const imageIndex = selections[scene.id];
                  const imageUrl = generateSceneImages(
                    scene.id,
                  )[imageIndex];
                  return (
                    <div
                      key={scene.id}
                      className="flex-shrink-0 w-32 space-y-1"
                    >
                      <div className="aspect-square rounded-md overflow-hidden border-2 border-blue-500 relative group">
                        <ImageWithFallback
                          src={imageUrl}
                          alt={scene.name}
                          className="w-full h-full object-cover"
                        />
                        <button
                          onClick={() =>
                            handleClearSelection(scene.id)
                          }
                          className="absolute top-1 right-1 bg-red-500 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <X className="size-3" />
                        </button>
                      </div>
                      <p className="text-xs text-center text-gray-600 truncate">
                        {scene.name}
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
              {SCENES.filter(
                (scene) => selections[scene.id] !== undefined,
              ).map((scene) => {
                const imageIndex = selections[scene.id];
                const imageUrl = generateSceneImages(scene.id)[
                  imageIndex
                ];
                return (
                  <div key={scene.id} className="space-y-2">
                    <div className="aspect-square rounded-lg overflow-hidden border-2 border-green-500">
                      <ImageWithFallback
                        src={imageUrl}
                        alt={scene.name}
                        className="w-full h-full object-cover"
                      />
                    </div>
                    <p className="text-sm text-center">
                      {scene.name}
                    </p>
                  </div>
                );
              })}
            </div>
          </Card>
        )}

        {/* シーン選択 */}
        <Accordion type="multiple" className="space-y-4">
          {SCENES.map((scene) => {
            const images = generateSceneImages(scene.id);
            const selectedImage = selections[scene.id] ?? null;

            return (
              <AccordionItem
                key={scene.id}
                value={`scene-${scene.id}`}
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
                        <span>{scene.id}</span>
                      )}
                    </div>
                    <div className="flex-1 text-left space-y-1 min-w-0">
                      <div>{scene.name}</div>
                      <div className="text-sm text-blue-600">
                        {scene.telop}
                      </div>
                      <p className="text-sm text-gray-600 pr-8">
                        {scene.description}
                      </p>
                    </div>
                    {selectedImage !== null && (
                      <div
                        onClick={(e) => {
                          e.stopPropagation();
                          handleClearSelection(scene.id);
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
                    sceneId={scene.id}
                    sceneName={scene.name}
                    images={images}
                    selectedImage={selectedImage}
                    onSelectImage={(imageIndex) =>
                      handleSelectImage(scene.id, imageIndex)
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