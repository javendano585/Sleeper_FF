from dataclasses import dataclass

@dataclass
class FantasyFootballUser:
    user_id: int
    display_name: str
    team_name: str
    is_commish: bool
    