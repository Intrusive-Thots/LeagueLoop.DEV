import pytest
from unittest.mock import MagicMock, patch
from services.automation.champ_select import predict_enemy_bans
from core.events import EventBus

@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine._bans_predicted = False
    
    def mock_lcu_request(method, endpoint, silent=True):
        req = MagicMock()
        req.status_code = 200
        
        if "puuid-1" in endpoint:
            # Yasuo (157) 2x, Yone (777) 1x
            req.json.return_value = {
                "games": {
                    "games": [
                        {"participants": [{"championId": 157}]},
                        {"participants": [{"championId": 157}]},
                        {"participants": [{"championId": 777}]}
                    ]
                }
            }
        elif "puuid-2" in endpoint:
            # Yasuo (157) 1x, Zed (238) 2x
            req.json.return_value = {
                "games": {
                    "games": [
                        {"participants": [{"championId": 157}]},
                        {"participants": [{"championId": 238}]},
                        {"participants": [{"championId": 238}]}
                    ]
                }
            }
        else:
            req.status_code = 404
            
        return req
        
    engine.lcu.request.side_effect = mock_lcu_request
    return engine

def test_predict_enemy_bans_hidden_identities(mock_engine):
    session = {
        "theirTeam": [
            {"puuid": ""},
            {"puuid": "0"},
            {}
        ]
    }
    
    with patch.object(EventBus, 'emit') as mock_emit:
        predict_enemy_bans(mock_engine, session)
        
        mock_emit.assert_called_once()
        args, _ = mock_emit.call_args
        assert args[0] == "ban_predictions"
        assert args[1]["hidden"] is True
        assert args[1]["predictions"] == []
        assert mock_engine._bans_predicted is True

def test_predict_enemy_bans_visible_identities(mock_engine):
    session = {
        "theirTeam": [
            {"puuid": "puuid-1"},
            {"puuid": "puuid-2"}
        ]
    }
    
    with patch.object(EventBus, 'emit') as mock_emit:
        predict_enemy_bans(mock_engine, session)
        
        mock_emit.assert_called_once()
        args, _ = mock_emit.call_args
        assert args[0] == "ban_predictions"
        assert args[1]["hidden"] is False
        
        preds = args[1]["predictions"]
        # Total counts: Yasuo (157) = 3, Zed (238) = 2, Yone (777) = 1
        assert len(preds) == 3
        assert preds[0]["championId"] == 157
        assert preds[0]["count"] == 3
        assert preds[1]["championId"] == 238
        assert preds[1]["count"] == 2
        assert preds[2]["championId"] == 777
        assert preds[2]["count"] == 1
