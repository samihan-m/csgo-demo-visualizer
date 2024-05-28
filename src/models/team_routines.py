from dataclasses import dataclass
from models.routine import Routine

@dataclass
class TeamRoutines:
    """A class tracking per-player routine lists for one team in a match. Assumes there are 5 players on a team."""
    routines: tuple[list[Routine], list[Routine], list[Routine], list[Routine], list[Routine]]

    @classmethod
    def from_routines_list(cls, routines: list[list[Routine]]) -> 'TeamRoutines':
        """Instantiates object from a list of routines. The list should be a list of lists, where each inner list contains the routines for a player."""
        if len(routines) != 5:
            raise ValueError(f"Invalid number of player routines received when creating Team object - must be 5, received {len(routines)}")
        return cls((routines[0], routines[1], routines[2], routines[3], routines[4]))

    def get_player_routines(self, player_index: int) -> list[Routine]:
        """Returns the routines for the given player index. Raises a ValueError if the player index is invalid."""
        if player_index < 0 or player_index >= 5:
            raise ValueError(f"Invalid player index {player_index} received when accessing routines in Team object - must be between 0 and 4 inclusive.")
        return self.routines[player_index]

@dataclass
class BothTeamsRoutines:
    """A small, wrapper class for holding routine-tracking objects for both teams in a match."""
    t_side: TeamRoutines
    ct_side: TeamRoutines