/**
 * File processing utilities for attachment handling.
 *
 * Classifies files by type, enforces size limits, and reads content
 * in the appropriate format (base64 for images/docs, text for code/text files).
 */

// ── File type classification ─────────────────────────────────────────

const IMAGE_TYPES = ["image/png", "image/jpeg", "image/gif", "image/webp"];

const TEXT_EXTENSIONS = [
  ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
  ".html", ".css", ".xml", ".csv", ".log", ".sh", ".c", ".cpp", ".java", ".go",
  ".rs", ".rb", ".php", ".sql", ".toml", ".ini",
];

const DOCUMENT_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];

// ── Size limits ──────────────────────────────────────────────────────

const MAX_IMAGE_SIZE = 4 * 1024 * 1024;   // 4MB
const MAX_TEXT_SIZE = 100 * 1024;          // 100KB
const MAX_DOC_SIZE = 5 * 1024 * 1024;     // 5MB

// ── Types ────────────────────────────────────────────────────────────

export type FileCategory = "image" | "text" | "document" | "generic";

export interface ProcessedFile {
  name: string;
  type: FileCategory;
  media_type: string;
  size: number;
  /** base64 for images/docs, text content for text files */
  content?: string;
  /** Object URL for image thumbnails (caller must revoke) */
  preview?: string;
}

// ── Helpers ──────────────────────────────────────────────────────────

/** Classify a file into one of our categories. */
export function classifyFile(file: File): FileCategory {
  if (IMAGE_TYPES.includes(file.type)) return "image";
  if (DOCUMENT_TYPES.includes(file.type)) return "document";

  const ext = `.${file.name.split(".").pop()?.toLowerCase()}`;
  if (TEXT_EXTENSIONS.includes(ext)) return "text";

  // Check MIME type fallback for text
  if (file.type.startsWith("text/")) return "text";

  return "generic";
}

/** Get the max allowed size for a file category. */
function maxSizeForCategory(category: FileCategory): number {
  switch (category) {
    case "image": return MAX_IMAGE_SIZE;
    case "text": return MAX_TEXT_SIZE;
    case "document": return MAX_DOC_SIZE;
    case "generic": return MAX_DOC_SIZE;
  }
}

/** Format bytes into a human-readable string. */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

/** Read a file as a base64-encoded data URL, returning only the base64 part. */
export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Strip the data:...;base64, prefix
      const base64 = result.split(",")[1];
      if (base64) {
        resolve(base64);
      } else {
        reject(new Error("Failed to extract base64 data"));
      }
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

/** Read a file as a data URL (including the data:...;base64, prefix). */
export function fileToDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

/** Read a file as text. */
export function fileToText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

// ── Main processing function ─────────────────────────────────────────

/**
 * Process a file for attachment: classify, validate size, read content.
 *
 * @throws Error if file exceeds size limit for its category
 */
export async function processFile(file: File): Promise<ProcessedFile> {
  const category = classifyFile(file);
  const maxSize = maxSizeForCategory(category);

  if (file.size > maxSize) {
    throw new Error(
      `File "${file.name}" is too large (${formatBytes(file.size)}). ` +
      `Maximum for ${category} files: ${formatBytes(maxSize)}.`
    );
  }

  const base: ProcessedFile = {
    name: file.name,
    type: category,
    media_type: file.type || "application/octet-stream",
    size: file.size,
  };

  switch (category) {
    case "image": {
      const content = await fileToBase64(file);
      const preview = URL.createObjectURL(file);
      return { ...base, content, preview };
    }
    case "text": {
      const content = await fileToText(file);
      return { ...base, content };
    }
    case "document": {
      const content = await fileToBase64(file);
      return { ...base, content };
    }
    case "generic":
      // Generic files: metadata only, no content extraction
      return base;
  }
}
