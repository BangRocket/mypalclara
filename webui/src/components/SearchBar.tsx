import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { commands, type SearchResult } from '../lib/bindings';
import { useUiStore } from '../stores';

interface SearchBarProps {
  className?: string;
}

export function SearchBar({ className = '' }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);

  const selectNote = useUiStore((s) => s.selectNote);

  // Debounced search with TanStack Query
  const { data: results, isLoading } = useQuery({
    queryKey: ['search', query],
    queryFn: async () => {
      if (!query.trim()) return [];
      const result = await commands.searchNotes(query, 20);
      if (result.status === 'error') {
        console.error('Search failed:', result.error);
        return [];
      }
      return result.data;
    },
    enabled: query.trim().length > 0,
    staleTime: 1000 * 30, // Cache for 30 seconds
  });

  const handleSelect = useCallback((noteId: number) => {
    selectNote(noteId);
    setQuery('');
    setIsOpen(false);
  }, [selectNote]);

  // Render snippet with HTML (from FTS5 <mark> tags)
  const renderSnippet = (snippet: string) => {
    return { __html: snippet };
  };

  return (
    <div className={`relative ${className}`}>
      <input
        type="text"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setIsOpen(true);
        }}
        onFocus={() => setIsOpen(true)}
        placeholder="Search notes..."
        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
      />

      {/* Dropdown results */}
      {isOpen && query.trim() && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-96 overflow-y-auto z-50">
          {isLoading && (
            <div className="px-4 py-3 text-sm text-gray-500">
              Searching...
            </div>
          )}

          {!isLoading && results?.length === 0 && (
            <div className="px-4 py-3 text-sm text-gray-500">
              No results found
            </div>
          )}

          {results?.map((result) => (
            <button
              key={result.id}
              onClick={() => handleSelect(result.id)}
              className="w-full text-left px-4 py-3 hover:bg-gray-100 border-b border-gray-100 last:border-b-0"
            >
              <div className="font-medium text-gray-900">{result.title}</div>
              <div
                className="text-sm text-gray-600 mt-1 [&>mark]:bg-yellow-200 [&>mark]:px-0.5"
                dangerouslySetInnerHTML={renderSnippet(result.snippet)}
              />
            </button>
          ))}
        </div>
      )}

      {/* Click outside to close */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
}
