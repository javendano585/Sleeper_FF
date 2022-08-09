from dataclasses import dataclass, field
import pandas as pd
import numpy as np
import time

from .ff_league import SleeperLeague

def _get_roster_spot(roster: pd.Series) -> str:
    player_id = roster.player_id
    if player_id in roster.starters: return 'starter'
    if player_id in roster.taxi: return 'taxi'
    if player_id in roster.reserve: return 'ir'
    return 'bench'

@dataclass
class SleeperLeagueAnalyzer:
    league_id: str
    league: SleeperLeague = field(init=False)
    _matchups: pd.DataFrame = field(init=False)
    _players: pd.DataFrame = field(init=False)
    _rosters: pd.DataFrame = field(init=False)
    _teams: pd.DataFrame = field(init=False)
    _users: pd.DataFrame = field(init=False)
    
    _ordered_roster_positions = ('QB', 'RB', 'WR', 'TE', 'K', 'DEF', 'DL', 'DL/LB', 'LB', 'DB/LB', 'DB')

    def __post_init__(self):
        self.league = SleeperLeague(self.league_id)
        self._matchups = None
        self._players = None
        self._rosters = None
        self._teams = None
        self._users = None

    @property
    def df_matchups(self) -> pd.DataFrame:
        if self._matchups is None:
            self.build_matchups_df()
            pass
        return self._matchups
    
    @property
    def df_players(self) -> pd.DataFrame:
        if self._players is None: 
            return self.build_players_df()
        return self._players

    @property
    def df_rosters(self) -> pd.DataFrame:
        if self._rosters is None:
            self.build_rosters_df()
            pass
        return self._rosters

    @property
    def df_teams(self) -> pd.DataFrame:
        if self._teams is None:
            self.build_teams_df()
            pass
        return self._teams

    @property
    def df_users(self) -> pd.DataFrame:
        if self._users is None:
            self.build_users_df()
            pass
        return self._users

    @property
    def league_info(self) -> str:
        return self.league.league_description

    def build_matchups_df(self) -> pd.DataFrame:
        # TODO
        pass

    @staticmethod
    def _drop_unused_positions(positions: list) -> list:
        positions = [pos for pos in positions if pos[0] != 'O']
        
        if 'LEO' in positions: positions.remove('LEO')
        if 'LS' in positions: positions.remove('LS')
        if 'P' in positions: positions.remove('P')
            
        return sorted(positions)

    def build_players_df(self) -> pd.DataFrame:
        players_dict = self.league.get_data('players')
        start_time = time.time()
        df = (
            pd.DataFrame(players_dict)
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
                    fantasy_pos = lambda df: df.fantasy_positions.apply(list).apply(SleeperLeagueAnalyzer._drop_unused_positions).apply('/'.join),
                    active = lambda df: df.active.fillna('False').astype(bool)
                    )
            .query('(fantasy_pos != "") and active')
            .drop(columns=['fantasy_positions', 'active'])
        )
        duration = time.time() - start_time
        print(f'Player DF build took {duration:.2} seconds')
        self._players = df
        return df

    def build_rosters_df(self) -> pd.DataFrame:
        rosters_dict = self.league.get_data('rosters')
        df_starters = (
            pd.DataFrame([(roster['owner_id'], roster['starters'])for roster in rosters_dict], columns=['owner_id', 'player_id'])
            .explode('player_id')
            .assign(starting_pos = lambda df: self.league.starting_positions * df.owner_id.nunique())
        )
        df = (
            pd.DataFrame(rosters_dict)
            .drop(columns=['player_map', 'metadata', 'co_owners', 'settings'])
            .explode('players')
            .rename(columns={'players': 'player_id'})
            .merge(df_starters, on=['owner_id', 'player_id'], how='left')
            .assign(roster_spot = lambda df: df.apply(_get_roster_spot, axis=1).astype('category'),
                    starting_pos = lambda df: df.starting_pos.fillna('NA').astype('category'))
            .drop(columns=['taxi', 'starters', 'reserve'])
            .astype({'owner_id': np.int64})
            [['owner_id' ,'roster_id', 'player_id', 'roster_spot', 'starting_pos']]
            )
        self._rosters = df
        return df

    def build_teams_df(self) -> pd.DataFrame:
        rosters_dict = self.league.get_data('rosters')
        df = (
            pd.DataFrame(rosters_dict)
            .astype({'owner_id': np.int64})
            .pipe(lambda df: df.assign(**df.settings.apply(pd.Series, dtype='str')))
            .pipe(lambda df: df.assign(**df.metadata.apply(pd.Series, dtype='str')))
            .astype({'fpts': np.int64, 'fpts_decimal': np.int64, 'fpts_against': np.int64, 'fpts_against_decimal': np.int64, 
                     'ppts': np.int64, 'ppts_decimal': np.int64})
            .drop(columns=['settings', 'metadata'])
            .assign(points_for = lambda df: df.fpts + (df.fpts_decimal / 100),
                    points_against = lambda df: df.fpts_against + (df.fpts_against_decimal / 100),
                    possible_points = lambda df: df.ppts + (df.ppts_decimal / 100),
                    rostered = lambda df: df.players.apply(len).astype(np.int8),
                    starters = lambda df: df.starters.apply(len).astype(np.int8),
                    taxi = lambda df: df.taxi.apply(len).astype(np.int8),
                    ir = lambda df: df.reserve.apply(len).astype(np.int8),
                    bench = lambda df: (df.rostered - df.starters - df.taxi - df.ir).astype(np.int8),
                    roster_locked = lambda df: (df.starters + df.bench > 40).astype(np.int8))
            [['owner_id', 'roster_id', 'division', 
              'wins', 'losses', 'ties', 
              'points_for', 'points_against', 'possible_points', 'record',
              'rostered', 'starters', 'bench', 'ir', 'taxi', 'roster_locked']]
        )
        self._teams = df
        return df

    def build_users_df(self) -> pd.DataFrame:
        users_dict = self.league.get_data('users')
        df = (
            pd.DataFrame(users_dict)
            .assign(team_name = lambda df: [d.get('team_name') for d in df.metadata],
                    is_commish = lambda df: df.is_owner.fillna(False).astype(np.int8))
            .assign(team_name = lambda df: np.where(df.team_name.isna(), 'Team ' + df.display_name, df.team_name))
            .astype({'user_id': np.int64})
            [['user_id', 'team_name', 'display_name', 'is_commish']]
            )
        self._users = df
        return df

    def _sort_roster_distribution_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        new_columns = [col for col in self._ordered_roster_positions if col in df.columns]
        df = df[['team_name', 'display_name', 'record'] + new_columns]
        df.columns.name = None
        return df

    def get_roster_distribution(self) -> pd.DataFrame:
        users = self.df_users
        teams = self.df_teams
        rosters = self.df_rosters
        players = self.df_players

        df = (
            rosters
            .merge(players[['player_id', 'fantasy_pos']], on='player_id', how='left')
            .groupby(['owner_id', 'fantasy_pos'], as_index=False)
            .size()
            .pivot_table(index='owner_id', columns='fantasy_pos', values='size', fill_value=0)
            .reset_index()
            .merge(users.rename(columns={'user_id': 'owner_id'})[['owner_id', 'team_name', 'display_name']], 
                   on='owner_id', how='left')
            .merge(teams[['owner_id', 'wins', 'losses', 'ties']], on='owner_id', how='left')
            .assign(record = lambda df: df.wins.astype(str) + '-' + df.losses.astype(str) + '-' + df.ties.astype(str))
            .pipe(self._sort_roster_distribution_columns)
        )
        return df

    def get_general_team_data(self) -> pd.DataFrame:
        users = self.df_users
        teams = self.df_teams
        df = (
            teams
            .merge(users.rename(columns={'user_id': 'owner_id'}), on='owner_id', how='left')
            [['team_name', 'display_name', 'wins', 'losses', 'ties', 'points_for', 'points_against', 'rostered']]
            .sort_values(['points_for', 'points_against'])
        )
        return df
