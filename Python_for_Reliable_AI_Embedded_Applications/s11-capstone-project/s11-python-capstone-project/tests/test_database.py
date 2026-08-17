from unittest.mock import patch, MagicMock
from app.utils.database import save_feedback_db


@patch("app.utils.database.psycopg2.connect")
def test_save_feedback_db_success(mock_connect):

    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    save_feedback_db("code", 5, "good")

    mock_cursor.execute.assert_called()
    mock_conn.commit.assert_called()


@patch("app.utils.database.psycopg2.connect")
def test_save_feedback_db_failure(mock_connect):

    mock_connect.side_effect = Exception("Connection failed")

    try:
        save_feedback_db("code", 5, "good")
    except Exception as e:
        assert "Connection failed" in str(e)