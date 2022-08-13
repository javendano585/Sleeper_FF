from turtle import width
from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State
import os

from ff_league_analyzer.ff_league_analyzer import SleeperLeagueAnalyzer
from pages import home, roster_distribution, weekly_scoring

# def get_data_for_dash(league_id: str) -> SleeperLeagueAnalyzer:
#     if league_id == '': return None
#     return SleeperLeagueAnalyzer(league_id=league_id)

def get_valid_leagues() -> list:
    valid_leagues = [
        {'label': 'Elite FF 2021', 'value': '736885905629024256'},
        {'label': 'USFL 2022', 'value': '786691248676257792'}
    ]
    return valid_leagues

def get_pages_for_dropdown() -> list:
    pages = [
        {'label': 'Home', 'value': 'home'},
        {'label': 'Roster Distribution', 'value': 'roster-distribution'},
        {'label': 'Weekly Scoring', 'value': 'weekly-scoring'},
    ]   
    return pages 

def update_league_analyzer(league_id: str):
    global league_analyzer

    if not league_id or league_id == '':
        league_analyzer = None
        return
    league_analyzer = SleeperLeagueAnalyzer(league_id=league_id)  

app = Dash(__name__, suppress_callback_exceptions=True)
server = app.server
league_analyzer: SleeperLeagueAnalyzer = None 

app.layout = html.Div([
    html.H1('Sleeper Fantasy Football Analyzer'),
    html.Div(
        [dcc.Dropdown(options=get_valid_leagues(), value='', id='league-dropdown')],
        style={'width': '35%'}
    ),
    html.H2('Please select a valid league to continue.', id='none-container'),
    # html.Div(
    #     dcc.Dropdown(options=get_pages_for_dropdown(), value='home', 
    #                  id='page-dropdown', clearable=False, 
    #                  style={'width': '35%'}), 
    #     id='page-dropdown-container'),
    dcc.Dropdown(
        options=get_pages_for_dropdown(), value='home', clearable=False, 
        id='page-dropdown'), 
    html.Br(),
    html.Div(id='page-container'),
])

# @app.callback(
#     Output('league-dropdown', 'value'),
#     Input('league-dropdown', 'value')
# )
# def league_dropdown_callback(value):
#     """ Maintains global league analyzer object."""
#     global league_analyzer
#     if not value:
#         league_analyzer = None
#         return ''
#     league_analyzer = get_data_for_dash(value)
#     return value

@app.callback(
    Output('none-container', 'style'),
    Output('page-dropdown', 'style'),
    Output('page-dropdown', 'value'),
    Input('league-dropdown', 'value')
)
def league_dropdown_callback(value):
    update_league_analyzer(value)

    # if not value or value == '':
    #     select_div = [html.H2('Please select a valid league to continue.')]
    #     page_selection = ''
    # else:
    #     select_div = [dcc.Dropdown(options=get_pages_for_dropdown(), value='home', id='page-dropdown', clearable=False)]
    #     page_selection = 'home'
    
    if not value or value == '':
        none_style = {'display': 'block'}
        page_dropdown_style = {'display': 'none'}
        page_selected = ''
    else:
        none_style = {'display': 'none'}
        page_dropdown_style = {'display': 'table', 'width': '35%'}
        page_selected = 'home'

    return none_style, page_dropdown_style, page_selected

@app.callback(
    Output('page-container', 'children'),
    Input('page-dropdown', 'value')
)
def page_dropdown_callback(page):
    if league_analyzer is None: return html.Div()

    match page:
        case 'home':
            return home.layout(league_analyzer)
        case 'roster-distribution':
            return roster_distribution.layout(league_analyzer)
        case 'weekly-scoring':
            return weekly_scoring.layout(league_analyzer)
    
    return html.Div()    

# @app.callback(
#     Output('league-home-container', 'children'),
#     Input('league-dropdown', 'value')
# )
# def update_home_div(value):
#     if value == '':
#         return [html.H2('Please select a valid league to continue.')]
#     home_div = [
#         html.H2(f'League: {league_analyzer.league_info}'),
#         dcc.Tabs(
#             id='league-tabs', value='tab-home',
#             children=[
#                 dcc.Tab(label='Home', value='tab-home', children=[home.layout(league_analyzer)]),
#                 dcc.Tab(label='Roster Distribution', value='tab-distribution', children=[roster_distribution.layout(league_analyzer)]),
#                 dcc.Tab(label='Weekly Scoring', value='tab-week-scoring', children=[weekly_scoring.layout(league_analyzer)])
#             ]
#         )
#     ]
#     return home_div

if __name__ == '__main__':
    debug_at_home = os.environ['COMPUTERNAME'] == 'LAPTOP-2J01O16G'
    app.run_server(debug=debug_at_home)