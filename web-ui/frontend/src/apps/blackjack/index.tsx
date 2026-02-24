/**
 * Blackjack app wrapper.
 *
 * The underlying Blackjack page component requires a `game` prop that was
 * previously provided by the router. In the ClaraOS windowed context, games
 * are launched from the Game Lobby which navigates via react-router. This
 * wrapper acts as a standalone entry point for the app registry — for now it
 * shows a placeholder directing users to the Game Lobby.
 */
export default function BlackjackApp({ windowId: _windowId }: { windowId: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
      <span className="text-5xl">{'\u{1F0CF}'}</span>
      <h2 className="text-lg font-semibold">Blackjack</h2>
      <p className="max-w-sm text-sm text-muted-foreground">
        Start a new Blackjack game from the <strong>Games</strong> lobby, or
        resume an in-progress game from your recent games list.
      </p>
    </div>
  );
}
