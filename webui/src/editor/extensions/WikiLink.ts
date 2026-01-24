import { Mark, mergeAttributes } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import Suggestion, { SuggestionOptions } from '@tiptap/suggestion';

export interface WikiLinkOptions {
  HTMLAttributes: Record<string, unknown>;
  onWikiLinkClick?: (noteId: number, title: string) => void;
  suggestion: Omit<SuggestionOptions, 'editor'>;
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    wikiLink: {
      setWikiLink: (attributes: { noteId: number; title: string }) => ReturnType;
      unsetWikiLink: () => ReturnType;
    };
  }
}

export const WikiLink = Mark.create<WikiLinkOptions>({
  name: 'wikiLink',

  priority: 1000, // High priority to take precedence over other marks

  addOptions() {
    return {
      HTMLAttributes: {
        class: 'wiki-link',
      },
      onWikiLinkClick: undefined,
      suggestion: {
        char: '[[',
        pluginKey: new PluginKey('wikiLinkSuggestion'),
        command: ({ editor, range, props }) => {
          // Insert the wiki link
          editor
            .chain()
            .focus()
            .deleteRange(range)
            .insertContent([
              {
                type: 'text',
                marks: [
                  {
                    type: 'wikiLink',
                    attrs: {
                      noteId: props.id,
                      title: props.title,
                    },
                  },
                ],
                text: props.title,
              },
              {
                type: 'text',
                text: ']] ',
              },
            ])
            .run();
        },
      },
    };
  },

  addAttributes() {
    return {
      noteId: {
        default: null,
        parseHTML: (element) => element.getAttribute('data-note-id'),
        renderHTML: (attributes) => {
          if (!attributes.noteId) return {};
          return { 'data-note-id': attributes.noteId };
        },
      },
      title: {
        default: null,
        parseHTML: (element) => element.getAttribute('data-title'),
        renderHTML: (attributes) => {
          return { 'data-title': attributes.title };
        },
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'a[data-type="wiki-link"]',
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'a',
      mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {
        'data-type': 'wiki-link',
        href: '#', // Prevent default navigation
      }),
      0,
    ];
  },

  addCommands() {
    return {
      setWikiLink:
        (attributes) =>
        ({ commands }) => {
          return commands.setMark(this.name, attributes);
        },
      unsetWikiLink:
        () =>
        ({ commands }) => {
          return commands.unsetMark(this.name);
        },
    };
  },

  addProseMirrorPlugins() {
    const plugins: Plugin[] = [];

    // Add suggestion plugin for autocomplete
    plugins.push(
      Suggestion({
        editor: this.editor,
        ...this.options.suggestion,
      })
    );

    // Add click handler plugin
    const { onWikiLinkClick } = this.options;
    if (onWikiLinkClick) {
      plugins.push(
        new Plugin({
          key: new PluginKey('wikiLinkClickHandler'),
          props: {
            handleDOMEvents: {
              click: (view, event) => {
                const target = event.target as HTMLElement;
                const link = target.closest('[data-type="wiki-link"]');
                if (link) {
                  event.preventDefault();
                  const noteId = link.getAttribute('data-note-id');
                  const title = link.getAttribute('data-title');
                  if (noteId && title) {
                    onWikiLinkClick(Number(noteId), title);
                    return true;
                  }
                }
                return false;
              },
            },
          },
        })
      );
    }

    return plugins;
  },
});
