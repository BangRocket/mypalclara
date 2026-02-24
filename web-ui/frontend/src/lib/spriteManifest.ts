/**
 * Sprite sheet manifest for Hex Character Pack.
 * Uses import.meta.glob to resolve Vite-hashed asset URLs.
 */

export const FRAME_SIZE = 60;

const ASSET_ROOT = "/src/assets/game-assets/characters/Hex Character Pack Full";

// Eagerly import all sprite PNGs — Vite resolves these to hashed URLs
const allSprites = import.meta.glob(
  "/src/assets/game-assets/characters/Hex Character Pack Full/**/*.png",
  { eager: true }
) as Record<string, { default: string }>;

/**
 * Resolve a sprite sheet URL by category folder and filename.
 * e.g. resolveSheetUrl("Eyes", "Blue.png") → "/assets/Blue-abc123.png"
 */
export function resolveSheetUrl(
  category: string,
  filename: string
): string | undefined {
  const key = `${ASSET_ROOT}/${category}/${filename}`;
  return allSprites[key]?.default;
}

export interface SpriteLayerDef {
  id: string;
  label: string;
  category: string; // folder name under asset root
  cols: number;
  rows: number;
  sheets: { filename: string; label: string }[];
  required?: boolean;
}

const COLOR_SHEETS = [
  { filename: "Blonde.png", label: "Blonde" },
  { filename: "Blue-Green.png", label: "Blue-Green" },
  { filename: "Blue.png", label: "Blue" },
  { filename: "Brown.png", label: "Brown" },
  { filename: "Dark Blue.png", label: "Dark Blue" },
  { filename: "Dark Brown.png", label: "Dark Brown" },
  { filename: "Dark.png", label: "Dark" },
  { filename: "Green.png", label: "Green" },
  { filename: "Light Brown.png", label: "Light Brown" },
  { filename: "Light Green.png", label: "Light Green" },
  { filename: "Lilac.png", label: "Lilac" },
  { filename: "Magent.png", label: "Magenta" },
  { filename: "Orange.png", label: "Orange" },
  { filename: "Pink.png", label: "Pink" },
  { filename: "Red.png", label: "Red" },
  { filename: "White.png", label: "White" },
];

export const SPRITE_LAYERS: SpriteLayerDef[] = [
  {
    id: "bg_layer",
    label: "Background",
    category: "BGs",
    cols: 3,
    rows: 4,
    sheets: COLOR_SHEETS,
  },
  {
    id: "base_layer",
    label: "Base",
    category: "Bases",
    cols: 3,
    rows: 4,
    sheets: [{ filename: "Model Sheet.png", label: "Default" }],
    required: true,
  },
  {
    id: "clothes_layer",
    label: "Clothes",
    category: "Clothes",
    cols: 3,
    rows: 4,
    sheets: COLOR_SHEETS,
  },
  {
    id: "eyes_layer",
    label: "Eyes",
    category: "Eyes",
    cols: 3,
    rows: 4,
    sheets: COLOR_SHEETS,
  },
  {
    id: "eyebrows_layer",
    label: "Eyebrows",
    category: "Eyebrows",
    cols: 3,
    rows: 4,
    sheets: COLOR_SHEETS,
  },
  {
    id: "mouth_layer",
    label: "Mouth",
    category: "Mouths",
    cols: 3,
    rows: 4,
    sheets: [
      { filename: "Mouth 1.png", label: "Style 1" },
      { filename: "Mouth 2.png", label: "Style 2" },
      { filename: "Mouth 3.png", label: "Style 3" },
      { filename: "Mouth 4.png", label: "Style 4" },
      { filename: "Mouth 5.png", label: "Style 5" },
      { filename: "Mouth 6.png", label: "Style 6" },
      { filename: "Mouth 7.png", label: "Style 7" },
      { filename: "Mouth 8.png", label: "Style 8" },
      { filename: "Mouth 9.png", label: "Style 9" },
      { filename: "Mouth 10.png", label: "Style 10" },
      { filename: "Mouth 11.png", label: "Style 11" },
      { filename: "Mouth 12.png", label: "Style 12" },
    ],
  },
  {
    id: "hair_layer",
    label: "Hair",
    category: "Hairs",
    cols: 6,
    rows: 6,
    sheets: [
      { filename: "Hair Sheet Black.png", label: "Black" },
      { filename: "Hair Sheet Blonde.png", label: "Blonde" },
      { filename: "Hair Sheet Blue-Green.png", label: "Blue-Green" },
      { filename: "Hair Sheet Blue.png", label: "Blue" },
      { filename: "Hair Sheet Brown 1.png", label: "Brown 1" },
      { filename: "Hair Sheet Brown 2.png", label: "Brown 2" },
      { filename: "Hair Sheet Brown 3.png", label: "Brown 3" },
      { filename: "Hair Sheet Dark Blue.png", label: "Dark Blue" },
      { filename: "Hair Sheet Green.png", label: "Green" },
      { filename: "Hair Sheet Light Green.png", label: "Light Green" },
      { filename: "Hair Sheet Lilac.png", label: "Lilac" },
      { filename: "Hair Sheet Magent.png", label: "Magenta" },
      { filename: "Hair Sheet Orange.png", label: "Orange" },
      { filename: "Hair Sheet Pink.png", label: "Pink" },
      { filename: "Hair Sheet Red.png", label: "Red" },
      { filename: "Hair Sheet White.png", label: "White" },
    ],
  },
];
