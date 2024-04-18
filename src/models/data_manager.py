from awpy.types import Game, GameRound, GameFrame, PlayerInfo
from pathlib import Path
import json
from pydantic import TypeAdapter, ValidationError
from models.player import Player
from models.round_stats import RoundStats
from models.team import Team
from models.team_type import TeamType
from models.routine import Routine
from typing import Generator, NewType

# For validating JSON data as a Game object
game_validator = TypeAdapter(Game)
# This function exists outside of DataManager in case we want to use it elsewhere
def __load_game_data(file_path: Path) -> Game:
    with open(file_path, 'r') as file:
        try:
            data = json.load(file)
            return game_validator.validate_python(data)
        except ValidationError as e:
            # TODO: Maybe handle this better
            raise e

# This NewType exists to make sure we don't pass any kind of number in for FrameCount.
# When creating a value of type FrameCount, we must be expressly aware that this variable we're making represents a frame count.
FrameCount = NewType('FrameCount', int)

class DataManager:
    data: Game

    def __init__(self, data: Game):
        self.data = data

    @classmethod
    def from_file(cls, file_path: Path):
        """Create a DataManager object from a JSON file containing a Game."""
        return cls(__load_game_data(file_path))
    
    def __get_game_rounds(self) -> list[GameRound]:
        """Returns the list of GameRound objects in the Game object. If there are no game rounds, raises a ValueError."""
        game_rounds = self.data['gameRounds']
        if game_rounds is None:
            raise ValueError("This game has no round data.")
        return game_rounds

    def get_game_round(self, round_index: int) -> GameRound:
        """Returns the GameRound object at the given index. If the index is out of bounds, raises a ValueError."""
        rounds = self.__get_game_rounds()
        if round_index >= len(rounds):
            raise ValueError(f"Round index {round_index} out of bounds (max index is {len(rounds) - 1})")
        return rounds[round_index]
    
    def __get_frames(self, round_id: int) -> list[GameFrame]:
        """Returns the list of GameFrame objects in the given round. If there are no frames in the round, raises a ValueError."""
        round_data = self.get_game_round(round_id)
        frames = round_data['frames']
        if frames is None:
            raise ValueError("No frames found in round")
        return frames

    def get_frame(self, round_id: int, frame_id: int) -> GameFrame:
        """Returns the GameFrame object at the given index in the given round. If the index is out of bounds, raises a ValueError."""
        frames = self.__get_frames(round_id)
        if frame_id >= len(frames):
            raise ValueError(f"Frame index {frame_id} out of bounds (max index is {len(frames) - 1})")
        return frames[frame_id]
    
    def get_map_name(self) -> str:
        """Returns the name of the map in the Game object."""
        return self.data['mapName']

    def __get_player_info_list(self, round_index: int, frame_index: int, team: TeamType) -> list[PlayerInfo]:
        """Returns the list of PlayerInfo objects for the given team in the given round and frame. If no player info is found, raises a ValueError."""
        player_info_list = self.get_frame(round_index, frame_index)[team.value]['players']
        if player_info_list is None:
            raise ValueError(f"No player info found for team {team.value} in round {round_index}, frame {frame_index}")
        return player_info_list
    
    def get_player_at_frame(self, player_index: int, team: TeamType, round_index: int, frame_index: int) -> PlayerInfo:
        """Returns the PlayerInfo object for the given player in the given team, round, and frame."""
        players = self.__get_player_info_list(round_index, frame_index, team)
        player = players[player_index] # NOTE: I don't know if the assumption that players are ordered the same every round is correct. If this is wrong, change how this is done.
        # To be fair, the old way (storing mappings from index to name, mappings which were generated in `get_all_team_routines`) also kind of relied on that assumption in that if untrue, the order of players could change across rounds and that would break the GUI.
        return player 
    
    def is_player_alive(self, player_index: int, team: TeamType, round_index: int, frame_index: int) -> bool:
        """Returns whether the given player is alive in the given team, round, and frame."""
        player = self.get_player_at_frame(player_index, team, round_index, frame_index)
        return player['isAlive']
    
    def get_round_stats(self, round_index: int, frame_index: int) -> RoundStats:
        """Returns a RoundStats object for the given round and frame."""
        round = self.get_game_round(round_index)
        frame = self.get_frame(round_index, frame_index)
        
        # Round-level stats
        winning_side = TeamType.from_str(round['winningSide'])
        round_end_reason = round['roundEndReason']

        # Frame-level stats
        clock_time = frame['clockTime']

        # CT-side stats
        opponents_alive = frame['ct']['alivePlayers']
        opponent_equipment_value = frame['ct']['teamEqVal']

        # T-side stats
        players = [Player.from_player_info(player_info) for player_info in self.__get_player_info_list(round_index, frame_index, TeamType.T)]

        # TODO: Understand why the CT-side stats and the T-side stats we're storing in RoundStats are asymmetric

        return RoundStats(
            players,
            winning_side,
            round_end_reason,
            opponents_alive,
            opponent_equipment_value,
            clock_time
        )
    
    def get_player_hp(self, player_index: int, team: TeamType, round_index: int, frame_index: int) -> int:
        """Returns the HP of the given player in the given team, round, and frame."""
        player = self.get_player_at_frame(player_index, team, round_index, frame_index)
        return player['hp']

    def __get_players_from_team_from_frame(self, frame: GameFrame, team: TeamType) -> list[PlayerInfo]:
        """Returns the list of T-side PlayerInfo objects from the given frame object. If no player info is found, raises a ValueError."""
        players = frame[team.value]['players']
        if players is None:
            raise ValueError(f"No player info found for team {team.value} in frame")
        return players
    
    def __get_players_from_team(self, round_index: int, frame_index: int, team: TeamType) -> list[PlayerInfo]:
        """Returns the list of T-side PlayerInfo objects for the given round and frame. If no player info is found, raises a ValueError."""
        frame = self.get_frame(round_index, frame_index)
        return self.__get_players_from_team_from_frame(frame, team)

    def get_all_team_routines(self, round_index: int, routine_length: FrameCount) -> tuple[Team, Team]:
        """Returns the routines for all players on both teams in the given round in the form of two Team objects."""
        frames = self.__get_frames(round_index)

        def batch_frames(frames: list[GameFrame], chunk_size: int) -> Generator[list[GameFrame], None, None]:
            frame_count = len(frames)
            for index in range(0, frame_count, chunk_size):
                yield frames[index:min(index + chunk_size, frame_count)]
        
        t_side_player_names = frozenset([player['name'] for player in self.__get_player_info_list(round_index, 0, TeamType.T)])
        ct_side_player_names = frozenset([player['name'] for player in self.__get_player_info_list(round_index, 0, TeamType.CT)])

        t_side_routines: dict[str, list[Routine]] = {player_name: list() for player_name in t_side_player_names}
        ct_side_routines: dict[str, list[Routine]] = {player_name: list() for player_name in ct_side_player_names}

        for chunk in batch_frames(frames, routine_length):
            for player_name in t_side_player_names: t_side_routines[player_name].append(Routine())
            for player_name in ct_side_player_names: ct_side_routines[player_name].append(Routine())
            for frame in chunk:
                for player in self.__get_players_from_team_from_frame(frame, TeamType.T):
                    t_side_routines[player['name']][-1].add_point(player['x'], player['y'])
                for player in self.__get_players_from_team_from_frame(frame, TeamType.CT):
                    ct_side_routines[player['name']][-1].add_point(player['x'], player['y'])
        t_side = Team.from_routines_list(list(t_side_routines.values()))
        ct_side = Team.from_routines_list(list(ct_side_routines.values()))
        return t_side, ct_side
                