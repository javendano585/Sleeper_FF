from dash import html, dash_table, dcc
import pandas as pd
import plotly.express as px

from ff_league_analyzer.ff_league_analyzer import SleeperLeagueAnalyzer

def layout(league_analyzer: SleeperLeagueAnalyzer):
    if league_analyzer is None: return html.Div()

    df = league_analyzer.get_weekly_scoring_by_position()

    fig = px.bar(df, 
                 x='start_points', y='team_name', color='pos', 
                 animation_frame='week',
                 title='Scoring by Position')
    fig.update_layout(
        xaxis_title=None,
        yaxis_title=None,
        legend_title=None
    )

    layout = html.Div([
        dcc.Graph(figure=fig)
    ])
    return layout