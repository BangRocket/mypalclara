import { useRef } from "react";
import { Paperclip, X } from "lucide-react";

export interface PendingFile {
  name: string;
  type: string;
  base64: string;
  size: number;
}

interface FileUploadProps {
  files: PendingFile[];
  onAdd: (files: PendingFile[]) => void;
  onRemove: (index: number) => void;
}

export function FileUpload({ files, onAdd, onRemove }: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList) return;

    const pending: PendingFile[] = [];
    for (const file of Array.from(fileList)) {
      // Max 10MB per file
      if (file.size > 10 * 1024 * 1024) continue;
      const base64 = await fileToBase64(file);
      pending.push({ name: file.name, type: file.type, base64, size: file.size });
    }
    onAdd(pending);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="p-2 text-text-muted hover:text-text-primary transition rounded-lg hover:bg-surface-overlay"
        title="Attach file"
      >
        <Paperclip size={18} />
      </button>
      <input
        ref={inputRef}
        type="file"
        multiple
        className="hidden"
        accept="image/*,.txt,.pdf,.md,.json,.csv"
        onChange={handleChange}
      />
      {files.map((f, i) => (
        <div key={i} className="flex items-center gap-1 bg-surface-overlay rounded-lg px-2 py-1 text-xs">
          <span className="text-text-secondary truncate max-w-[120px]">{f.name}</span>
          <button onClick={() => onRemove(i)} className="text-text-muted hover:text-danger">
            <X size={12} />
          </button>
        </div>
      ))}
    </div>
  );
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Strip the data URL prefix (e.g., "data:image/png;base64,")
      resolve(result.split(",")[1] || result);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
