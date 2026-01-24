import { forwardRef, useEffect, useImperativeHandle, useState } from 'react';
import type { NoteTitle } from '../../lib/bindings';

interface WikiLinkSuggestionListProps {
  items: NoteTitle[];
  command: (item: NoteTitle) => void;
}

export interface WikiLinkSuggestionListRef {
  onKeyDown: (props: { event: KeyboardEvent }) => boolean;
}

export const WikiLinkSuggestionList = forwardRef<
  WikiLinkSuggestionListRef,
  WikiLinkSuggestionListProps
>((props, ref) => {
  const [selectedIndex, setSelectedIndex] = useState(0);

  const selectItem = (index: number) => {
    const item = props.items[index];
    if (item) {
      props.command(item);
    }
  };

  useEffect(() => {
    setSelectedIndex(0);
  }, [props.items]);

  useImperativeHandle(ref, () => ({
    onKeyDown: ({ event }) => {
      if (event.key === 'ArrowUp') {
        setSelectedIndex((prev) =>
          prev <= 0 ? props.items.length - 1 : prev - 1
        );
        return true;
      }
      if (event.key === 'ArrowDown') {
        setSelectedIndex((prev) =>
          prev >= props.items.length - 1 ? 0 : prev + 1
        );
        return true;
      }
      if (event.key === 'Enter') {
        selectItem(selectedIndex);
        return true;
      }
      return false;
    },
  }));

  if (props.items.length === 0) {
    return (
      <div className="wiki-link-suggestions bg-white border border-gray-200 rounded-lg shadow-lg p-2 text-sm text-gray-500">
        No notes found
      </div>
    );
  }

  return (
    <div className="wiki-link-suggestions bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
      {props.items.map((item, index) => (
        <button
          key={item.id}
          className={`w-full text-left px-3 py-2 text-sm ${
            index === selectedIndex
              ? 'bg-blue-100 text-blue-900'
              : 'text-gray-700 hover:bg-gray-100'
          }`}
          onClick={() => selectItem(index)}
        >
          {item.title}
        </button>
      ))}
    </div>
  );
});

WikiLinkSuggestionList.displayName = 'WikiLinkSuggestionList';
