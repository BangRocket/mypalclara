export type EntryId = string;

export interface Position {
  x: number;
  y: number;
}

export type FSEntryType = 'file' | 'directory' | 'app-shortcut';

interface BaseEntry {
  id: EntryId;
  name: string;
  parentId: EntryId | null;
  type: FSEntryType;
  iconPosition: Position;
  createdAt: Date;
  updatedAt: Date;
  disableDelete?: boolean;
  disableCopy?: boolean;
  icon?: string;
}

export interface FSFile extends BaseEntry {
  type: 'file';
  extension: string;
  content: string;
}

export interface FSDirectory extends BaseEntry {
  type: 'directory';
  children: EntryId[];
}

export interface FSAppShortcut extends BaseEntry {
  type: 'app-shortcut';
  appId: string;
  extension: '.app';
}

export type FSEntry = FSFile | FSDirectory | FSAppShortcut;
