from dataclasses import dataclass, field
from datetime import date
import json
from pathlib import Path
import pickle
from typing import Any

from sleeper_wrapper import League, Players

@dataclass
class SleeperLeague:
    league_id: str
    name: str = field(init=False)
    season: str = field(init=False)
    sleeper_league: League = field(init=False)

    league_info: dict = field(default_factory=dict)
    players: dict = field(default_factory=dict)
    rosters: dict = field(default_factory=dict)
    users: dict = field(default_factory=dict)
    matchups: dict = field(default_factory=dict)

    @property
    def league_description(self):
        return f'{self.name} ({self.season})'

    def __post_init__(self) -> None:
        self.sleeper_league = League(self.league_id)
        self._pull_league_data()

    def get_data(self, data: str) -> dict:
        match data:
            case 'league':
                return self.league_info
            case 'players':
                return self._get_players()
            case 'rosters':
                if self.rosters == dict():
                    self._pull_rosters()
                return self.rosters
            case 'users':
                if self.users == dict():
                    self._pull_users()
                return self.users
            case 'matchups':
                if self.matchups == dict():
                    self._pull_matchups()
                return self.matchups
            case _:
                return {}
    
    def refresh_data(self, data_to_refresh) -> None:
        if 'league' in data_to_refresh:
            self._pull_league_data()
        if 'players' in data_to_refresh:
            self._pull_players()
        if 'rosters' in data_to_refresh:
            self._pull_rosters()
        if 'users' in data_to_refresh:
            self._pull_users()
        if 'matchups' in data_to_refresh:
            self._pull_matchups()

    def _get_players(self) -> dict:
        """
        Checks if we have today's players already in a pickle file, otherwise pulls them
        """
        if self.players == dict():
            current_players_file = self._get_players_filename()
            if current_players_file.is_file():
                print('Reading current players file.')
                with open(current_players_file, 'rb') as f:
                    self.players = pickle.load(f, protocol=pickle.HIGHEST_PROTOCOL)
            else:
                self._pull_players()
                with open(current_players_file, 'wb') as f:
                    pickle.dump(self.players, f)
        return self.players
    
    def _get_players_filename(self) -> Path:
        today = date.today().strftime(f'%Y%m%d')
        temp_folder = Path('.') / 'data'
        current_players_file = f'sleeper_players_{today}.pickle'
        self._clear_old_player_files(temp_folder, current_players_file)
        return temp_folder / current_players_file

    def _clear_old_player_files(self, folder: Path, active_file: str) -> None:
        for x in folder.glob('sleeper_players_*.json'):
            if x.is_file() and x.name != active_file:
                x.unlink()
    
    def _pull_league_data(self) -> None:
        league_info = self.sleeper_league.get_league()
        self.league_info = league_info
        self.name = league_info.get('name', '')
        self.season = league_info.get('season', '')
        self.starting_positions = [pos for pos in league_info['roster_positions'] if pos != 'BN']

    def _pull_players(self) -> None:
        print('Pulling players from Sleeper API.')
        players = Players()
        self.players = players.get_all_players()
    
    def _pull_rosters(self) -> None:
        rosters_dict = self.sleeper_league.get_rosters()
        for roster in rosters_dict:
            # Replaces empty roster groups with empty list.
            for roster_slot in ['starters', 'taxi', 'reserve']:
                roster[roster_slot] = [] if roster.get(roster_slot) is None else roster[roster_slot]
            # These roster variables don't exists in the preseason.
            roster_settings = roster['settings']
            for single_setting in ['fpts_decimal', 'fpts_against', 'fpts_against_decimal', 'ppts', 'ppts_decimal']:
                if single_setting not in roster_settings: roster_settings[single_setting] = 0
            if 'record' not in roster_settings: roster_settings['record'] = ''
        self.rosters = rosters_dict

    def _pull_users(self) -> None:
        self.users = self.sleeper_league.get_users()

    def _pull_matchups(self) -> None:
        self.matchups = {week: self.sleeper_league.get_matchups(week) for week in range(1, 19)}