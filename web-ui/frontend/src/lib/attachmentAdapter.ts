/**
 * Custom AttachmentAdapter for the Clara gateway.
 *
 * Handles images, text/code files, PDFs, and generic files. Uses assistant-ui's
 * adapter interface so the built-in drop zone, file picker, preview, and remove
 * UI all work automatically.
 *
 * The adapter processes files when added (for immediate preview) and converts
 * them to gateway-compatible format when sent.
 */

import type { AttachmentAdapter } from "@assistant-ui/core/adapters/attachment";
import type { Attachment, PendingAttachment, CompleteAttachment } from "@assistant-ui/core/types/attachment";
import type { ThreadUserMessagePart } from "@assistant-ui/core/types/message";
import { classifyFile, fileToBase64, fileToText, fileToDataURL, type FileCategory } from "@/utils/fileProcessing";

// ── Size limits ──────────────────────────────────────────────────────

const MAX_IMAGE_SIZE = 4 * 1024 * 1024;   // 4MB
const MAX_TEXT_SIZE = 100 * 1024;          // 100KB
const MAX_DOC_SIZE = 5 * 1024 * 1024;     // 5MB

function maxSizeForCategory(category: FileCategory): number {
  switch (category) {
    case "image": return MAX_IMAGE_SIZE;
    case "text": return MAX_TEXT_SIZE;
    case "document": return MAX_DOC_SIZE;
    case "generic": return MAX_DOC_SIZE;
  }
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

// ── Gateway attachment format ────────────────────────────────────────

/** The format the gateway WebSocket expects for attachments. */
export interface GatewayAttachment {
  filename: string;
  content_type: string;
  data: string;       // base64 for images/docs, text content for text files
  size: number;
}

// ── Adapter ──────────────────────────────────────────────────────────

/**
 * Map our file categories to assistant-ui attachment types.
 * assistant-ui uses "image" | "document" | "file" for display purposes.
 */
function categoryToAttachmentType(category: FileCategory): "image" | "document" | "file" {
  switch (category) {
    case "image": return "image";
    case "text": return "document";
    case "document": return "document";
    case "generic": return "file";
  }
}

/**
 * Custom attachment adapter that handles all file types Clara supports.
 *
 * - Images: validates size, creates preview, sends as base64
 * - Text/code: validates size, reads content, sends as text
 * - PDF/docx: validates size, sends as base64
 * - Generic: metadata only
 */
export class ClaraAttachmentAdapter implements AttachmentAdapter {
  // Accept all file types
  accept = "*";

  async add(state: { file: File }): Promise<PendingAttachment> {
    const { file } = state;
    const category = classifyFile(file);
    const maxSize = maxSizeForCategory(category);

    if (file.size > maxSize) {
      throw new Error(
        `File "${file.name}" is too large (${formatBytes(file.size)}). ` +
        `Maximum for ${category} files: ${formatBytes(maxSize)}.`
      );
    }

    return {
      id: `${file.name}-${Date.now()}`,
      type: categoryToAttachmentType(category),
      name: file.name,
      contentType: file.type || "application/octet-stream",
      file,
      status: { type: "requires-action", reason: "composer-send" },
    };
  }

  async send(attachment: PendingAttachment): Promise<CompleteAttachment> {
    const { file } = attachment;
    const category = classifyFile(file);
    const content: ThreadUserMessagePart[] = [];

    switch (category) {
      case "image": {
        const dataUrl = await fileToDataURL(file);
        content.push({ type: "image", image: dataUrl });
        break;
      }
      case "text": {
        const text = await fileToText(file);
        content.push({
          type: "text",
          text: `<attachment name="${attachment.name}">\n${text}\n</attachment>`,
        });
        break;
      }
      case "document": {
        const base64 = await fileToBase64(file);
        content.push({
          type: "file",
          data: base64,
          mimeType: file.type,
          filename: attachment.name,
        });
        break;
      }
      case "generic": {
        // Generic files: include as file part with base64 data
        const base64 = await fileToBase64(file);
        content.push({
          type: "file",
          data: base64,
          mimeType: file.type || "application/octet-stream",
          filename: attachment.name,
        });
        break;
      }
    }

    return {
      ...attachment,
      status: { type: "complete" },
      content,
    };
  }

  async remove(_attachment: Attachment): Promise<void> {
    // No cleanup needed -- object URLs are managed by assistant-ui's useFileSrc
  }
}

// ── Conversion helper ────────────────────────────────────────────────

/**
 * Convert a CompleteAttachment to the gateway's wire format.
 *
 * Called by ChatRuntimeProvider.onNew to transform assistant-ui attachments
 * into the shape the gateway WebSocket expects.
 */
export function attachmentToGateway(attachment: CompleteAttachment): GatewayAttachment | null {
  const contentType = attachment.contentType || "application/octet-stream";

  // Extract data from the content parts
  for (const part of attachment.content) {
    if (part.type === "image") {
      // Image parts have a data URL -- extract the base64 portion
      const dataUrl = part.image;
      const base64Match = dataUrl.match(/^data:[^;]+;base64,(.+)$/);
      const data = base64Match ? base64Match[1] : dataUrl;
      return {
        filename: attachment.name,
        content_type: contentType,
        data,
        size: attachment.file?.size ?? data.length,
      };
    }

    if (part.type === "text") {
      return {
        filename: attachment.name,
        content_type: contentType,
        data: part.text,
        size: attachment.file?.size ?? new Blob([part.text]).size,
      };
    }

    if (part.type === "file") {
      return {
        filename: ("filename" in part ? part.filename : attachment.name) ?? attachment.name,
        content_type: ("mimeType" in part ? part.mimeType : contentType) ?? contentType,
        data: part.data,
        size: attachment.file?.size ?? part.data.length,
      };
    }
  }

  return null;
}
