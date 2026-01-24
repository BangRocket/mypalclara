import { ReactRenderer } from '@tiptap/react';
import tippy, { Instance as TippyInstance } from 'tippy.js';
import Fuse from 'fuse.js';
import { commands, type NoteTitle } from '../../lib/bindings';
import {
  WikiLinkSuggestionList,
  WikiLinkSuggestionListRef,
} from '../components/WikiLinkSuggestionList';

export const wikiLinkSuggestion = {
  items: async ({ query }: { query: string }): Promise<NoteTitle[]> => {
    // Fetch all note titles from backend
    const result = await commands.getAllNoteTitles();
    if (result.status === 'error') {
      console.error('Failed to fetch note titles:', result.error);
      return [];
    }

    const notes = result.data;

    // If no query, return first 10 notes
    if (!query) {
      return notes.slice(0, 10);
    }

    // Fuzzy search with Fuse.js
    const fuse = new Fuse(notes, {
      keys: ['title'],
      threshold: 0.3,
      distance: 100,
    });

    return fuse.search(query).map((r) => r.item).slice(0, 10);
  },

  render: () => {
    let component: ReactRenderer<WikiLinkSuggestionListRef> | null = null;
    let popup: TippyInstance[] | null = null;

    return {
      onStart: (props: any) => {
        component = new ReactRenderer(WikiLinkSuggestionList, {
          props,
          editor: props.editor,
        });

        if (!props.clientRect) return;

        popup = tippy('body', {
          getReferenceClientRect: props.clientRect,
          appendTo: () => document.body,
          content: component.element,
          showOnCreate: true,
          interactive: true,
          trigger: 'manual',
          placement: 'bottom-start',
        });
      },

      onUpdate(props: any) {
        component?.updateProps(props);

        if (!props.clientRect || !popup?.[0]) return;

        popup[0].setProps({
          getReferenceClientRect: props.clientRect,
        });
      },

      onKeyDown(props: any) {
        if (props.event.key === 'Escape') {
          popup?.[0]?.hide();
          return true;
        }
        return component?.ref?.onKeyDown(props) ?? false;
      },

      onExit() {
        popup?.[0]?.destroy();
        component?.destroy();
      },
    };
  },
};
