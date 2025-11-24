import { useState } from 'react';
import { Check } from 'lucide-react';
import { ImageWithFallback } from './figma/ImageWithFallback';

interface SceneSelectorProps {
  sceneId: number;
  sceneName: string;
  images: string[];
  selectedImage: number | null;
  onSelectImage: (imageIndex: number) => void;
}

export function SceneSelector({
  sceneId,
  sceneName,
  images,
  selectedImage,
  onSelectImage,
}: SceneSelectorProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg">
          {sceneName}
        </h3>
        {selectedImage !== null && (
          <div className="flex items-center gap-2 text-green-600">
            <Check className="size-5" />
            <span className="text-sm">選択済み</span>
          </div>
        )}
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {images.map((imageUrl, index) => (
          <button
            key={`scene-${sceneId}-image-${index}`}
            type="button"
            onClick={() => onSelectImage(index)}
            className={`relative aspect-square rounded-lg overflow-hidden transition-all hover:scale-105 ${
              selectedImage === index
                ? 'ring-4 ring-blue-500 shadow-lg'
                : 'ring-1 ring-gray-200 hover:ring-2 hover:ring-blue-300'
            }`}
          >
            <ImageWithFallback
              src={imageUrl}
              alt={`${sceneName} - 候補 ${index + 1}`}
              className="w-full h-full object-cover"
            />
            {selectedImage === index && (
              <div className="absolute inset-0 bg-blue-500/20 flex items-center justify-center">
                <div className="bg-blue-500 text-white rounded-full p-2">
                  <Check className="size-6" />
                </div>
              </div>
            )}
            <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-sm py-1 px-2 text-center">
              候補 {index + 1}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
