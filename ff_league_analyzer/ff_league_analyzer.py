from collections import Counter
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import time

from typing import Tuple
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
    _data_frames: dict = field(init=False, default_factory=dict)
    _figures: dict = field(init=False, default_factory=dict)
    
    # _ordered_roster_positions = ('QB', 'RB', 'WR', 'TE', 'K', 'DEF', 'DL', 'DL/LB', 'LB', 'DB/LB', 'DB')

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

    def _roster_distribution(self, week: pd.DataFrame) -> Counter:
        player_pos_map = dict(zip(self.df_players.player_id, self.df_players.fantasy_pos))

        starters = set(week.starters)
        bench_points = 0
        valid_starters = 0
        for player, points in week.players_points.items():
            if player not in starters:
                bench_points += points
            elif points > 0:
                valid_starters += 1
        
        ignore_players = ['0']
        start_pos_order = [pos.lower() for pos in pd.unique(self.league.starting_positions).tolist()]
        pos_order = [pos.lower() for pos in self.league.ordered_roster_positions]
        # start_pos = Counter({'start_' + pos: 0 for pos in start_pos_order})
        # roster_pos = Counter({'roster_' + pos: 0 for pos in pos_order})
        starters_score = Counter({'start_' + pos: 0 for pos in start_pos_order})
        pos_score = Counter({pos + '_score': 0 for pos in pos_order})
        
        roster_stats = Counter({'bench_points': bench_points, 'active_starters': valid_starters})
        for pos, score in zip(self.league.starting_positions, week.starters_points):
            starters_score.update({('start_' + pos.lower()): score})
        # start_pos.update(Counter(['start_' + player_pos_map.get(starter, '').lower() for starter in starters if starter not in ignore_players]))
        # roster_pos.update(Counter(['roster_' + player_pos_map.get(player, '').lower() for player in week.players if player not in ignore_players]))
        pos_scores = [(player_pos_map.get(player,'').lower() + '_score', score)
                          for player, score in week.players_points.items()
                          if (player not in ignore_players)]
        pos_score.update(pd.DataFrame(pos_scores, columns=['player', 'score']).groupby('player').score.sum().to_dict())
        
        return_counter = Counter()
        return_counter.update(roster_stats)
        return_counter.update(starters_score)
        # return_counter.update(start_pos)
        # return_counter.update(roster_pos)
        return_counter.update(pos_score)
        return return_counter

    def _adjust_weekly_data_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        start_columns = ['roster_id', 'week', 'matchup_id', 'points', 'bench_points', 'active_starters']
        drop_columns = ['starters', 'starters_points', 'players', 'players_points', 'custom_points']
        new_column_order = start_columns + [col for col in df.columns if col not in (start_columns + drop_columns)]
        df = df[new_column_order]
        return df

    def build_matchups_df(self) -> pd.DataFrame:
        start_time = time.time()
        matchups_dict = self.league.get_data('matchups')
        duration = time.time() - start_time
        print(f'Get matchups dict in {duration:.2} seconds.')
        df_list = []
        for week, week_dict in matchups_dict.items():
            df_week = (
                pd.DataFrame(week_dict)
                .assign(week = week,
                        matchup_id = lambda df: df.matchup_id.fillna(-1).astype(np.int8))
                .pipe(lambda df: df.assign(**pd.DataFrame(df.apply(self._roster_distribution, axis=1).tolist())))
                .pipe(self._adjust_weekly_data_columns)
            )
            df_list.append(df_week)
        df_scores = pd.concat(df_list).reset_index(drop=True)
        df = (
            df_scores        
            .merge(df_scores[['week', 'matchup_id', 'roster_id', 'points']], on=['week', 'matchup_id'], suffixes=('', '_opp'), how='left')
            .rename(columns={'roster_id_opp': 'opponent_id', 'points_opp': 'opp_points'})
            .query('roster_id != opponent_id')
            .assign(result = lambda df: np.select([df.matchup_id == -1,
                                                df.points > df.opp_points, 
                                                df.points == df.opp_points, 
                                                df.points < df.opp_points],
                                                ['No matchup', 'Win', 'Tie', 'Loss']),
                    opponent_id = lambda df: np.where(df.matchup_id == -1, -1, df.opponent_id),
                    opp_points = lambda df: np.where(df.matchup_id == -1, 0, df.opp_points))
        )
        self._matchups = df
        return df

    @staticmethod
    def _clean_player_info(player_info: dict) -> dict:
        ignore_keys = {
            'espn_id', 'fantasy_data_id', 'gsis_id', 'pandascore_id', 'rotowire_id', 'rotoworld_id', 
            'sleeper_id', 'sportradar_id', 'stats_id', 'swish_id', 'yahoo_id', 
            'high_school', 'college',
            'birth_city', 'birth_country', 'birth_date', 'birth_state', 
            'hashtag', 'height', 'injury_body_part', 'injury_notes', 'injury_start_date', 
            'news_updated', 'number',
            'practice_description', 'practice_participation', 
            'search_full_name', 'search_first_name', 'search_last_name', 'search_rank', 'sport', 
            'weight'
        }
        cleaned_player_info = {k: v for k,v in player_info.items() if k not in ignore_keys}
        return cleaned_player_info

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
        players_cleaned = {player: self._clean_player_info(player_info) 
                            for player, player_info 
                            in players_dict.items() 
                            if player_info.get('active')}
        df = (
            pd.DataFrame(players_cleaned)
            .T
            .rename_axis('sleeper_id')
            .reset_index()
            # .drop(columns=['hashtag', 'news_updated', 'sport',
            #                'sleeper_id', 'pandascore_id', 'rotowire_id', 'espn_id', 'yahoo_id', 
            #                'sportradar_id', 'stats_id', 'fantasy_data_id', 'swish_id', 'gsis_id', 'rotoworld_id',
            #                'birth_date', 'birth_city', 'birth_state', 'birth_country', 
            #                'height', 'weight', 'high_school', 'college',
            #                'search_first_name', 'search_last_name', 'search_full_name'])
            .assign(fantasy_positions = lambda df: df.fantasy_positions.apply(lambda d: d if isinstance(d, list) else []),
                    fantasy_pos = lambda df: df.fantasy_positions.apply(list).apply(self._drop_unused_positions).apply('/'.join),
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
        new_columns = [col for col in self.league.ordered_roster_positions if col in df.columns]
        df = df[['team_name', 'display_name', 'record'] + new_columns]
        df.columns.name = None
        return df

    def get_roster_distribution(self) -> pd.DataFrame:
        if 'roster-distribution' in self._data_frames:
            return self._data_frames['roster-distribution']

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
        self._data_frames['roster-distribution'] = df
        return df

    def get_general_team_data(self) -> pd.DataFrame:
        if 'team-general' in self._data_frames:
            return self._data_frames['team-general']

        users = self.df_users
        teams = self.df_teams
        df = (
            teams
            .merge(users.rename(columns={'user_id': 'owner_id'}), on='owner_id', how='left')
            [['team_name', 'display_name', 'wins', 'losses', 'ties', 'points_for', 'points_against', 'rostered']]
            .sort_values(['points_for', 'points_against'], ascending=False)
        )
        self._data_frames['team-general'] = df
        return df

    def get_weekly_scoring(self) -> pd.DataFrame:
        if 'weekly_scoring' in self._data_frames:
            return self._data_frames['weekly_scoring']

        matchups = self.df_matchups
        users = self.df_users
        teams = self.df_teams
        start_time = time.time()
        df = (
            matchups
            .assign(week_score = lambda df: df.filter(like='start_', axis=1).sum(axis=1))
            .melt(id_vars=['roster_id', 'week', 'week_score'], 
                value_vars=[col for col in matchups.columns if 'start_' in col], 
                var_name='pos', 
                value_name='start_points')
            .assign(pos = lambda df: df.pos.str.replace('start_', '').str.upper())
            .merge(teams[['owner_id', 'roster_id']], on='roster_id', how='left')
            .merge(users.rename(columns={'user_id': 'owner_id'})[['owner_id', 'team_name']], 
                on='owner_id', how='left')
            .sort_values(['week', 'week_score', 'roster_id'])
        )
        duration = time.time() - start_time
        print(f'Weekly Scoring DF build took {duration:.2} seconds')
        self._data_frames['weekly_scoring'] = df
        return df

    def get_weekly_summary_plot(self) -> go.Figure:
        if 'weekly_scoring_summary' in self._figures:
            return self._figures['weekly_scoring_summary']

        df = (
            self.get_weekly_scoring()
            .groupby(['team_name', 'week'], as_index=False)
            .agg(week_score=('start_points', 'sum'))
            .assign(total_score = lambda df: df.groupby(['team_name']).week_score.transform('sum'))
            .sort_values(['total_score', 'week'])
        )

        start_time = time.time()
        fig = px.line(
            df, 
            x='week', y='week_score', color='team_name', 
            hover_name='team_name',
            hover_data={'week': True, 'week_score': True, 'team_name': False},
            labels={'week': 'Week', 'week_score': 'Score', 'team_name': 'Team'},
            title='Scoring by Week'
        )
        duration = time.time() - start_time
        print(f'Weekly Summary Figure build took {duration:.2} seconds')

        # Switching to go.Figure, as it's currently building 25x faster than px.line.
        # https://github.com/plotly/plotly.py/issues/1743
        start_time = time.time()
        fig = go.Figure(
            layout_yaxis_range=[0, round(df.week_score.max() + 10, 1)],
        )
        for team in reversed(df.team_name.unique().tolist()):
            dff = df.query('team_name == @team')
            fig.add_trace(go.Scatter(
                x=dff.week,
                y=dff.week_score,
                mode='lines',
                name=team,
                hovertemplate= f'<b>{team}' + '</b><br><br>Week: %{x}<br>Score: %{y}<extra></extra>',
                line=dict(width=0.75)
            ))
        fig.update_layout(
            title='Scoring by Week'
        )
        duration2 = time.time() - start_time
        print(f'Weekly Summary go.Figure build took {duration2:.2} seconds')
        print(f'go.Figure is {(duration / duration2):.2f}x faster than px.line.')

        self._figures['weekly_scoring_summary'] = fig
        return fig

    def get_weekly_scoring_by_position_plot(self) -> go.Figure:
        if 'weekly_scoring_by_pos' in self._figures:
            return self._figures['weekly_scoring_by_pos']

        df = self.get_weekly_scoring()

        start_time = time.time()
        fig = px.bar(
            df, 
            x='start_points', y='team_name', color='pos', 
            hover_name='team_name',
            hover_data={'week': True, 'pos': True, 'start_points': True, 'team_name': False},
            labels={'week': 'Week', 'pos': 'Position', 'start_points': 'Points'},
            animation_frame='week',
            title='Scoring by Position'
        )
        fig.update_layout(
            xaxis_title=None,
            yaxis_title=None,
            legend_title=None
        )
        duration = time.time() - start_time
        print(f'Weekly Scoring by Pos Figure build took {duration:.2} seconds')

        # start_time = time.time()
        # fig = go.Figure(
        #     layout_yaxis_range=[0, round(df.week_score.max() + 10, 1)],
        # )
        # for pos in reversed(df.pos.unique().tolist()):
        #     dff = df.query('pos == @pos')
        #     fig.add_trace(go.Bar(
        #         x=dff.start_points,
        #         y=dff.team_name,
        #         name=pos,
        #         hovertemplate= '<b>%{team_name}</b><br><br>Week: %{x}<br>Score: %{y}<extra></extra>'
        #     ))
        # fig.update_layout(
        #     title='Scoring by Position'
        # )
        # duration2 = time.time() - start_time
        # print(f'Weekly Scoring go.Figure build took {duration2:.2} seconds')
        # print(f'go.Figure is {(duration / duration2):.2f}x faster than px.line.')

        self._figures['weekly_scoring_by_pos'] = fig
        return fig