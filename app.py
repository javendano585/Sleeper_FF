from dash import Dash, dcc, html
from dash.dependencies import Input, Output
import os

from ff_league_analyzer.ff_league_analyzer import SleeperLeagueAnalyzer
from pages import home, roster_distribution, weekly_scoring

def get_data_for_dash(league_id: str) -> SleeperLeagueAnalyzer:
    if league_id == '': return None
    return SleeperLeagueAnalyzer(league_id=league_id)

def get_valid_leagues() -> list:
    valid_leagues = [
        {'label': 'Elite FF 2021', 'value': '736885905629024256'},
        {'label': 'USFL 2022', 'value': '786691248676257792'}
    ]
    return valid_leagues

app = Dash(__name__, suppress_callback_exceptions=True)
server = app.server
league_analyzer: SleeperLeagueAnalyzer = None 

app.layout = html.Div([
    html.H1('Sleeper Fantasy Football Analyzer'),
    html.Div(
        [dcc.Dropdown(options=get_valid_leagues(), value='', id='league-dropdown')],
        style={'width': '35%'}
    ),
    html.Div(
        id='league-home-container',
        style={'width': '85%'}),
])

@app.callback(
    Output('league-dropdown', 'value'),
    Input('league-dropdown', 'value')
)
def dropdown_callback(value):
    """ Maintains global league analyzer object."""
    global league_analyzer
    if not value:
        league_analyzer = None
        return ''
    league_analyzer = get_data_for_dash(value)
    return value

@app.callback(
    Output('league-home-container', 'children'),
    Input('league-dropdown', 'value')
)
def update_home_div(value):
    if value == '':
        return [html.H2('Please select a valid league to continue.')]
    home_div = [
        html.H2(f'League: {league_analyzer.league_info}'),
        dcc.Tabs(
            id='league-tabs', value='tab-home',
            children=[
                dcc.Tab(label='Home', value='tab-home', children=[home.layout(league_analyzer)]),
                dcc.Tab(label='Roster Distribution', value='tab-distribution', children=[roster_distribution.layout(league_analyzer)]),
                dcc.Tab(label='Weekly Scoring', value='tab-week-scoring', children=[weekly_scoring.layout(league_analyzer)])
            ]
        )
    ]
    return home_div

if __name__ == '__main__':
    debug_at_home = os.environ['COMPUTERNAME'] == 'LAPTOP-2J01O16G'
    app.run_server(debug=debug_at_home)