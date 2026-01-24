import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Calendar } from '@/components/ui/calendar';
import { Button } from '@/components/ui/button';
import { commands } from '@/lib/bindings';
import { useUiStore } from '@/stores';
import { format, parseISO, startOfToday } from 'date-fns';

export function CalendarPanel() {
  const queryClient = useQueryClient();
  const selectDate = useUiStore((state) => state.selectDate);
  const selectNote = useUiStore((state) => state.selectNote);
  const selectedDate = useUiStore((state) => state.selectedDate);
  const [month, setMonth] = useState<Date>(new Date());

  // Fetch all dates with daily notes
  const { data: dailyNotesResult } = useQuery({
    queryKey: ['dailyNoteDates'],
    queryFn: async () => {
      const result = await commands.listDailyNoteDates();
      if (result.status === 'ok') {
        return result.data;
      }
      throw new Error(result.error);
    },
  });

  const dailyNotes = dailyNotesResult ?? [];

  // Create a Set of dates that have notes for quick lookup
  const datesWithNotes = new Set(
    dailyNotes.map((note) => note.daily_note_date)
  );

  // Handle date selection
  const handleSelect = async (date: Date | undefined) => {
    if (!date) return;

    const dateStr = format(date, 'yyyy-MM-dd');
    selectDate(dateStr);

    // Get or create the daily note
    const result = await commands.getOrCreateDailyNote(dateStr);
    if (result.status === 'ok') {
      selectNote(result.data.id);
      // Invalidate the daily notes query to update calendar dots
      queryClient.invalidateQueries({ queryKey: ['dailyNoteDates'] });
    }
  };

  // Navigate to today
  const handleToday = () => {
    const today = startOfToday();
    setMonth(today);
    handleSelect(today);
  };

  // Custom day render to show dots on dates with notes
  const modifiers = {
    hasNote: (date: Date) => {
      const dateStr = format(date, 'yyyy-MM-dd');
      return datesWithNotes.has(dateStr);
    },
  };

  const modifiersStyles = {
    hasNote: {
      fontWeight: 'bold' as const,
      textDecoration: 'underline',
    },
  };

  // Currently selected date as Date object
  const selected = selectedDate ? parseISO(selectedDate) : undefined;

  return (
    <div className="p-4 border-b border-gray-200">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-gray-700">Calendar</h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleToday}
          className="text-xs h-7"
        >
          Today
        </Button>
      </div>
      <Calendar
        mode="single"
        selected={selected}
        onSelect={handleSelect}
        month={month}
        onMonthChange={setMonth}
        modifiers={modifiers}
        modifiersStyles={modifiersStyles}
        className="rounded-md border border-gray-200"
      />
      <p className="text-xs text-gray-500 mt-2 text-center">
        Click a date to open its daily note
      </p>
    </div>
  );
}
