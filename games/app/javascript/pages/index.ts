import Lobby from "./Lobby"
import Blackjack from "./games/Blackjack"
import Checkers from "./games/Checkers"
import History from "./History"
import Replay from "./Replay"

const pages: Record<string, any> = {
  Lobby,
  "games/Blackjack": Blackjack,
  "games/Checkers": Checkers,
  History,
  Replay,
}

export default pages
