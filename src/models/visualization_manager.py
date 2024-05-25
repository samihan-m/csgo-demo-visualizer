from matplotlib.collections import PathCollection
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from awpy.visualization.plot import plot_map, position_transform
from matplotlib.lines import Line2D
from matplotlib.text import Text

from models.data_manager import DataManager
from models.routine import DEFAULT_ROUTINE_LENGTH, Routine
from models.side_type import SideType

# Hyperparameter for the number of frames in the past to include in the visualization. Currently set to the default routine length but there's no reason it has to be.
# Probably shouldn't be much greater than 5 or so as the opacity calculations in the code drawing the frame will make the oldest frames almost invisible.
# It's very doable to just change the opacity function if we want, though.
VISUALIZED_ROUTINE_LENGTH = DEFAULT_ROUTINE_LENGTH

class VisualizationManager:
    dm: DataManager
    fig: Figure
    axes: Axes
    lines: list[Line2D] # Tracks lines for precise removal
    path_collections: list[PathCollection] # Tracks scatter plot points for precise removal
    text: list[Text] # Tracks text for precise removal

    current_round_index: int
    current_frame_index: int

    def __init__(self, dm: DataManager, fig: Figure, axes: Axes):
        self.dm = dm
        self.fig = fig
        self.axes = axes
        self.lines = list()
        self.path_collections = list()
        self.text = list()
        
        self.current_round_index = 0
        self.current_frame_index = 0
    
    @classmethod
    def from_data_manager(cls, dm: DataManager) -> 'VisualizationManager':
        """Create a VisualizationManager object from an instantiated DataManager object."""
        fig, axes = plot_map(
            map_name=dm.get_map_name(),
            map_type='simpleradar',
            dark=True
        )
        return cls(dm, fig, axes)

    def render(self):
        """Render the map. Primarily for use in CLI contexts."""
        self.fig.show()

    def draw_routine(self, routine: Routine, fmt: str = "", **kwargs) -> Axes:
        """Draws a routine on the map. `fmt` is a format string following matplotlib fmt string notation, and kwargs can be used to add additional format options (overwriting any conflicting options from the format string)."""

        map_name = self.dm.get_map_name()

        transformed_x = [position_transform(map_name, xpos, 'x') for xpos in routine.x]
        transformed_y = [position_transform(map_name, ypos, 'y') for ypos in routine.y]

        self.lines.extend(self.axes.plot(transformed_x, transformed_y, fmt, **kwargs))
        return self.axes
    
    def _clear_all_drawings(self):
        """Clears all drawings from the figure."""
        for line in self.lines:
            line.remove()
        self.lines.clear()
        for collection in self.path_collections:
            collection.remove()
        self.path_collections.clear()
        for text in self.text:
            text.remove()
        self.text.clear()

    def _draw_frame(self) -> Axes:
        """Draws the positions of players at the current frame. Raises a ValueError if the current round index or the current frame index is out of bounds."""
        max_rounds = self.dm.get_round_count()
        max_frames = self.dm.get_frame_count(self.current_round_index)
        if self.current_round_index >= max_rounds:
            raise ValueError(f"Round index {self.current_round_index} is out of bounds. Max rounds: {max_rounds}")
        if self.current_frame_index >= max_frames:
            raise ValueError(f"Frame index {self.current_frame_index} is out of bounds. Max frames: {max_frames}")

        self._clear_all_drawings()

        map_name = self.dm.get_map_name()

        # Plot player positions up to VISUALIZED_ROUTINE_LENGTH frames back (VISUALIZED_ROUTINE_LENGTH + 1 frames total). Plot previous frames with decreasing opacity.
        for frame_index_subtrahend in range(0, VISUALIZED_ROUTINE_LENGTH + 1):
            # Ensure we don't try to access a frame index that doesn't exist
            if self.current_frame_index - frame_index_subtrahend < 0:
                break
            
            player_info_lists = self.dm.get_player_info_lists(self.current_round_index, self.current_frame_index - frame_index_subtrahend)
            t_side_players = player_info_lists[SideType.T]
            ct_side_players = player_info_lists[SideType.CT]

            transformed_t_x = [position_transform(map_name, player['x'], 'x') for player in t_side_players]
            transformed_t_y = [position_transform(map_name, player['y'], 'y') for player in t_side_players]
            self.path_collections.append(self.axes.scatter(transformed_t_x, transformed_t_y, c='goldenrod', alpha=(1 - 0.1*frame_index_subtrahend)))

            transformed_ct_x = [position_transform(map_name, player['x'], 'x') for player in ct_side_players]
            transformed_ct_y = [position_transform(map_name, player['y'], 'y') for player in ct_side_players]
            self.path_collections.append(self.axes.scatter(transformed_ct_x, transformed_ct_y, c='lightblue', alpha=(1 - 0.1*frame_index_subtrahend)))

            # Draw player names only for the most recent frame
            if frame_index_subtrahend == 0:
                for index, player in enumerate(t_side_players):
                    self.text.append(self.axes.text(transformed_t_x[index], transformed_t_y[index], player['name'], fontsize=10, ha='center', va='bottom', color='white'))
                for index, player in enumerate(ct_side_players):
                    self.text.append(self.axes.text(transformed_ct_x[index], transformed_ct_y[index], player['name'], fontsize=10, ha='center', va='bottom', color='white'))

        bomb_info = self.dm.get_bomb_info(self.current_round_index, self.current_frame_index)
        bomb_x = position_transform(map_name, bomb_info['x'], 'x')
        bomb_y = position_transform(map_name, bomb_info['y'], 'y')
        self.path_collections.append(self.axes.scatter(bomb_x, bomb_y, c='red')) # Maybe pick a better color for the bomb as fire grenades are also red

        # Plot grenades
        current_frame_tick = self.dm.get_frame(self.current_round_index, self.current_frame_index)['tick']

        grenade_color_map = {
            'Incendiary Grenade': 'red',
            'Molotov': 'red',
            'Smoke Grenade': 'gray',
            'HE Grenade': 'green',
            'Flashbang': 'gold',
        }

        thrower_color_map = {
            SideType.T: 'goldenrod',
            SideType.CT: 'lightblue',
        }

        for grenade in self.dm.get_grenade_events(self.current_round_index):
            if grenade['throwTick'] <= current_frame_tick <= grenade['destroyTick']:
                start_x = position_transform(map_name, grenade['throwerX'], 'x')
                start_y = position_transform(map_name, grenade['throwerY'], 'y')
                end_x = position_transform(map_name, grenade['grenadeX'], 'x')
                end_y = position_transform(map_name, grenade['grenadeY'], 'y')
                grenade_color = grenade_color_map[grenade['grenadeType']]
                thrower_color = thrower_color_map[SideType.from_str(grenade['throwerSide'])]
                self.lines.extend(self.axes.plot([start_x, end_x], [start_y, end_y], color=grenade_color))
                self.path_collections.append(self.axes.scatter(end_x, end_y, color=grenade_color, edgecolors=thrower_color))

        return self.axes
    
    def draw_round_start(self, round_index: int) -> Axes:
        """Draws the positions of players at the start of the given round number."""
        self.current_round_index = round_index
        self.current_frame_index = 0
        return self._draw_frame()
    
    def revisualize(self):
        """Revisualizes the current round and frame."""
        return self._draw_frame()

    def progress_visualization(self) -> bool:
        """Progresses the visualization by one frame. Returns True if the visualization is still playing, False if it has reached the end."""
        max_rounds = self.dm.get_round_count()
        max_frames = self.dm.get_frame_count(self.current_round_index)
        if self.current_round_index >= max_rounds - 1:
            return False
        if self.current_frame_index >= max_frames - 1:
            self.current_round_index += 1
            self.current_frame_index = 0
            if self.current_round_index >= max_rounds:
                return False
        self.current_frame_index += 1
        self._draw_frame()
        return True
        