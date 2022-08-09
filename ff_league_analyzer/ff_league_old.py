import pandas as pd
import numpy as np

from pathlib import Path
import requests

from dataclasses import dataclass, field
from typing import Protocol, Tuple

from ff_user import FantasyFootballUser
# from ff_roster import FantasyFootballRoster
from sleeper_wrapper import League

@dataclass
class FantasyFootballLeague(Protocol):
    name: str
    year: int
    host: str
    league_id: str
    datapath: Path = None
    files: dict = field(default_factory=dict)
    dfs: dict = field(default_factory=dict)

    positions_sort = ['QB', 'RB', 'RB/WR', 'WR', 'TE', 'K', 'DEF', 'DL', 'DL/LB', 'LB', 'DB/LB', 'DB']
  
    def set_datafiles(self, datapath: Path, file_dict: dict) -> None:
        if datapath.is_dir():
            self.datapath = datapath
        else:
            raise ValueError('Datapath mush be a valid directory.')

        for k, v in file_dict.items():
            self.files[k] = datapath / v

    def get_league_users(self, refresh: bool) -> list[FantasyFootballUser]:
        ...
    
    def _get_datafile(self, filetype: str):
        datafile = self.files.get(filetype)
        if datafile is None:
            raise ValueError(f'The datafile for <{filetype}> isn\'t set.')
        return datafile

class SleeperLeague(FantasyFootballLeague):
    
    def __init__(self, name: str, year: int, league_id: int) -> None:
        super().__init__(name, year, 'Sleeper', league_id)
        self._build_league_info()

    def _build_league_info(self):
        sleeper_league = f'https://api.sleeper.app/v1/league/{self.league_id}'
        response = requests.get(sleeper_league)
        league_json = response.json()
        
        roster_positions = np.unique(league_json['roster_positions']).tolist()
        if 'BN' in roster_positions: roster_positions.remove('BN')
        if 'FLEX' in roster_positions: roster_positions.remove('FLEX')
        self.roster_positions = roster_positions

    def get_league_users(self, refresh: bool = False) -> pd.DataFrame:
        """
        Returns a dataframe with all the users in the league, including those not assigned to a team.
        Columns = [user_id, team_name, display_name, is_commish]
        """
        
        if (self.dfs.get('users') is not None) and (not refresh):
            print('Returning current users dataframe.')
            df = self.dfs.get('users')
        else:
            print('Pulling users from Sleeper API.')
            sleeper_league_users = f'https://api.sleeper.app/v1/league/{self.league_id}/users'
            response = requests.get(sleeper_league_users)
            users_json = response.json()
            df = (
                pd.DataFrame(users_json)
                .drop(columns=['settings', 'is_bot', 'avatar'])
                .assign(team_name = lambda df: [d.get('team_name') for d in df.metadata],
                        is_commish = lambda df: df.is_owner.fillna(False).astype(np.int8))
                .astype({'league_id': np.int64, 'user_id': np.int64})
                [['user_id', 'team_name', 'display_name', 'is_commish']]
            )
            self.dfs['users'] = df
        return df

    @staticmethod
    def _get_roster_spot(roster: pd.Series) -> str:
        player_id = roster.player_id
        if player_id in roster.starters: return 'starter'
        if player_id in roster.taxi: return 'taxi'
        if player_id in roster.reserve: return 'ir'
        return 'bench'
    
    def build_rosters_and_teams(self) -> None:
        """
        Calls the sleeper rosters API and builds the rosters and teams dataframes
        """

        print('Pulling roster data from Sleeper API.')
        sleeper_rosters = f'https://api.sleeper.app/v1/league/{self.league_id}/rosters'
        response = requests.get(sleeper_rosters)
        rosters_json = response.json()
        
        for roster in rosters_json:
            # Replaces empty roster groups with empty list.
            for roster_slot in ['starters', 'taxi', 'reserve']:
                roster[roster_slot] = [] if roster.get(roster_slot) is None else roster[roster_slot]

            # These roster variables don't exists in the preseason.
            roster_settings = roster['settings']
            for single_setting in ['fpts_decimal', 'fpts_against', 'fpts_against_decimal', 'ppts', 'ppts_decimal']:
                if single_setting not in roster_settings: roster_settings[single_setting] = 0
            if 'record' not in roster_settings: roster_settings['record'] = ''
        
        df_rosters = (
            pd.DataFrame(rosters_json)
            .drop(columns=['player_map', 'metadata', 'co_owners', 'settings'])
            .explode('players')
            .rename(columns={'players': 'player_id'})
            .assign(roster_spot = lambda df: df.apply(SleeperLeague._get_roster_spot, axis=1).astype('category'))
            .drop(columns=['taxi', 'starters', 'reserve'])
            .astype({'owner_id': np.int64})
            [['owner_id' ,'roster_id', 'player_id', 'roster_spot']]
        )
        
        df_teams = (
            pd.DataFrame(rosters_json)
            # [['owner_id', 'roster_id', 'settings', 'metadata']]
            .astype({'owner_id': np.int64})
            .pipe(lambda df: df.assign(**df.settings.apply(pd.Series, dtype='str')))
            .pipe(lambda df: df.assign(**df.metadata.apply(pd.Series, dtype='str')))
            .astype({'fpts': np.int64, 'fpts_decimal': np.int64, 'fpts_against': np.int64, 'fpts_against_decimal': np.int64, 
                     'ppts': np.int64, 'ppts_decimal': np.int64})
            # .drop(columns=['settings', 'metadata'])
            .assign(points_for = lambda df: df.fpts + (df.fpts_decimal / 100),
                    points_against = lambda df: df.fpts_against + (df.fpts_against_decimal / 100),
                    possible_points = lambda df: df.ppts + (df.ppts_decimal / 100),
                    rostered = lambda df: df.players.apply(len).astype(np.int8),
                    starters = lambda df: df.starters.apply(len).astype(np.int8),
                    taxi = lambda df: df.taxi.apply(len).astype(np.int8),
                    ir = lambda df: df.reserve.apply(len).astype(np.int8),
                    bench = lambda df: (df.rostered - df.starters - df.taxi - df.ir).astype(np.int8),
                    roster_locked = lambda df: (df.starters + df.bench > 40).astype(np.int8))
            [['owner_id', 'roster_id', 
                'division', 'wins', 'losses', 'ties', 
                'points_for', 'points_against', 'possible_points', 'record',
                'rostered', 'starters', 'bench', 'ir', 'taxi', 'roster_locked']]
        )
        self.dfs['rosters'] = df_rosters
        self.dfs['teams'] = df_teams

    def get_league_rosters(self, refresh: bool = False) -> pd.DataFrame:
        """
        Returns a dataframe with the current roster of each team and where they are located.
        Columns = [owner_id, roster_id, player_id, roster_spot]
        """

        if (self.dfs.get('rosters') is not None) and (not refresh):
            print('Returning current rosters dataframes.')
            df_rosters = self.dfs.get('rosters')
        else:
            self.build_rosters_and_teams()
            df_rosters = self.dfs.get('rosters')

        return df_rosters

    def get_league_teams(self, refresh: bool = False) -> pd.DataFrame:
        """
        Returns a dataframe with current team data
        Columns = [owner_id, roster_id, division,
                   wins, losses, ties,
                   points_for, points_against, possible_points, record, 
                   starters, bench, ir, taxi, roster_locked]

        """

        if (self.dfs.get('teams') is not None) and (not refresh):
            print('Returning current teams dataframe.')
            df_teams = self.dfs.get('teams')
        else:
            self.build_rosters_and_teams()
            df_teams = self.dfs.get('teams')

        return df_teams

    @staticmethod
    def _drop_unused_positions(positions: list) -> list:
        positions = [pos for pos in positions if pos[0] != 'O']
        
        if 'LEO' in positions: positions.remove('LEO')
        if 'LS' in positions: positions.remove('LS')
        if 'P' in positions: positions.remove('P')
            
        return sorted(positions)
        
    def get_league_players(self, refresh: bool = False) -> pd.DataFrame:
        players_filepath = self._get_datafile('players')

        if (self.dfs.get('players') is not None) and (not refresh):
            print('Returning current players dataframe.')
            df_players = self.dfs.get('players')
        elif players_filepath.exists() and players_filepath.is_file() and (not refresh):
            print('Reading parquet file for players.')
            df_players = pd.read_parquet(players_filepath)
            self.dfs['players'] = df_players
        else:
            print('Pulling new player list from Sleeper API.')
            sleeper_players = 'https://api.sleeper.app/v1/players/nfl'
            response = requests.get(sleeper_players)
            players_json = response.json()
            df_players = (
                pd.DataFrame(players_json)          
                .T
                .rename_axis('sleeper_id')
                .reset_index()
                .drop(columns=['hashtag', 'news_updated', 'sport',
                               'sleeper_id', 'pandascore_id', 'rotowire_id', 'espn_id', 'yahoo_id', 
                               'sportradar_id', 'stats_id', 'fantasy_data_id', 'swish_id', 'gsis_id', 'rotoworld_id',
                               'birth_date', 'birth_city', 'birth_state', 'birth_country', 
                               'height', 'weight', 'high_school', 'college',
                               'search_first_name', 'search_last_name', 'search_full_name'])
                .assign(fantasy_positions = lambda df: df.fantasy_positions.apply(lambda d: d if isinstance(d, list) else []),
                        fantasy_pos = lambda df: df.fantasy_positions.apply(list).apply(SleeperLeague._drop_unused_positions).apply('/'.join),
                        active = lambda df: df.active.fillna('False').astype(bool)
                        )
                .query('(fantasy_pos != "") and active')
                .drop(columns=['fantasy_positions', 'active'])
            )
            df_players.to_parquet(players_filepath)
            self.dfs['players'] = df_players
        return df_players
    