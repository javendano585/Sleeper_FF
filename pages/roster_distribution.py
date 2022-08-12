from dash import html, dash_table
import pandas as pd

from ff_league_analyzer.ff_league_analyzer import SleeperLeagueAnalyzer

def get_external_column_names(df: pd.DataFrame) -> list:
    """
    Converts position columns to uppercase.
    """
    name_mapping = {
        'team_name': 'Team Name',
        'display_name': 'User',
        'record': 'Record'
        }
    names = [{'id': col, 'name': name_mapping.get(col, col.upper())} for col in df.columns]
    return names

def get_style_cell_conditional(df: pd.DataFrame) -> list:
    """Sets specific widths for some columns (default is 5%)."""
    width_mapping = {
        'team_name': '15%',
        'display_name': '10%',
        'record': '10%'
    }
    widths = [{'if': {'column_id': col}, 'width': width} for col, width in width_mapping.items()]
    return widths

def get_style_data_conditional(df: pd.DataFrame) -> list:
    style_list = [
        {
            'if': {'row_index': 'odd'}, 
            'backgroundColor': 'rgb(255, 225, 200)'
        },
        {
            'if': {'column_id': ['team_name', 'display_name']}, 
            'textAlign': 'left'
        }
    ]
    highlight_top = [
        {
            'if': {
                'filter_query': f'{{{col}}} >= {value}',
                'column_id': col
            },
            'fontWeight': 'bold',
            'border': '3px solid rgb(0, 200, 0)'
        } for (col, value) in df.quantile(0.9).iteritems()]
    return style_list + highlight_top

def get_style_header_conditional() -> list:
    style_list = [
        {
            'if': {'column_id': ['team_name', 'display_name']}, 
            'textAlign': 'left'
        }
    ]
    return style_list

def layout(league_analyzer: SleeperLeagueAnalyzer):
    if league_analyzer is None: return html.Div()

    df = league_analyzer.get_roster_distribution()
    print('roster_distribution tab')

    layout = html.Div([
        dash_table.DataTable(
            df.to_dict('records'),
            columns=get_external_column_names(df),
            sort_action='native',
            fill_width=True,
            style_cell={
                'width': '5%'
            },
            style_cell_conditional=get_style_cell_conditional(df),
            style_data_conditional=get_style_data_conditional(df),
            style_header={
                'backgroundColor': 'rgb(200, 100, 0)',
                'color': 'black',
                'fontWeight': 'bold',
            },
            style_header_conditional=get_style_header_conditional(),
        )
    ])
    return layout