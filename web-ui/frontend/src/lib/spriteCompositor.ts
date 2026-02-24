/**
 * Canvas compositing engine for layered pixel-art sprites.
 * Draws sprite layers bottom-to-top, extracting frames from sprite sheets.
 */

import { FRAME_SIZE } from "./spriteManifest";

export interface SpriteLayer {
  imageSrc: string;
  row: number;
  col: number;
}

const imageCache = new Map<string, HTMLImageElement>();

function loadImage(src: string): Promise<HTMLImageElement> {
  const cached = imageCache.get(src);
  if (cached?.complete) return Promise.resolve(cached);

  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      imageCache.set(src, img);
      resolve(img);
    };
    img.onerror = reject;
    img.src = src;
  });
}

/**
 * Composite sprite layers onto a canvas.
 * Draws each layer's frame (60×60) extracted at (col*60, row*60),
 * scaled to fill the canvas.
 */
export async function compositeSprite(
  canvas: HTMLCanvasElement,
  layers: SpriteLayer[],
  size: number
): Promise<void> {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  canvas.width = size;
  canvas.height = size;
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, size, size);

  for (const layer of layers) {
    try {
      const img = await loadImage(layer.imageSrc);
      ctx.drawImage(
        img,
        layer.col * FRAME_SIZE,
        layer.row * FRAME_SIZE,
        FRAME_SIZE,
        FRAME_SIZE,
        0,
        0,
        size,
        size
      );
    } catch {
      // Skip layers that fail to load
    }
  }
}
