import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { commands } from '@/lib/bindings';
import { useUiStore } from '@/stores';
import { format, addDays, subDays, parseISO, startOfToday } from 'date-fns';
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon } from 'lucide-react';

export function DateNavigation() {
  const queryClient = useQueryClient();
  const selectedDate = useUiStore((state) => state.selectedDate);
  const viewingDailyNote = useUiStore((state) => state.viewingDailyNote);
  const selectDate = useUiStore((state) => state.selectDate);
  const selectNote = useUiStore((state) => state.selectNote);

  // Only show when viewing a daily note
  if (!viewingDailyNote || !selectedDate) {
    return null;
  }

  const currentDate = parseISO(selectedDate);

  const navigateToDate = async (date: Date) => {
    const dateStr = format(date, 'yyyy-MM-dd');
    selectDate(dateStr);

    const result = await commands.getOrCreateDailyNote(dateStr);
    if (result.status === 'ok') {
      selectNote(result.data.id);
      queryClient.invalidateQueries({ queryKey: ['dailyNoteDates'] });
    }
  };

  const handlePrevDay = () => navigateToDate(subDays(currentDate, 1));
  const handleNextDay = () => navigateToDate(addDays(currentDate, 1));
  const handleToday = () => navigateToDate(startOfToday());

  const isToday = format(currentDate, 'yyyy-MM-dd') === format(startOfToday(), 'yyyy-MM-dd');

  return (
    <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-200 bg-gray-50">
      <CalendarIcon className="w-4 h-4 text-gray-500" />
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7"
        onClick={handlePrevDay}
        title="Previous day"
      >
        <ChevronLeft className="h-4 w-4" />
      </Button>
      <span className="text-sm font-medium min-w-[140px] text-center">
        {format(currentDate, 'MMMM d, yyyy')}
      </span>
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7"
        onClick={handleNextDay}
        title="Next day"
      >
        <ChevronRight className="h-4 w-4" />
      </Button>
      {!isToday && (
        <Button
          variant="outline"
          size="sm"
          className="ml-2 h-7 text-xs"
          onClick={handleToday}
        >
          Today
        </Button>
      )}
    </div>
  );
}
