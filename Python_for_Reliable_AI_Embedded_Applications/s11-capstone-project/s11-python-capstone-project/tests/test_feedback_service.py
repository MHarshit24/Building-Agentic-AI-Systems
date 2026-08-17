from unittest.mock import patch, mock_open
from app.services.feedback_service import save_feedback


class DummyFeedback:
    code = "print('hi')"
    rating = 5
    comment = "good"


@patch("app.services.feedback_service.save_feedback_db")
@patch("builtins.open", new_callable=mock_open)
def test_save_feedback_success(mock_file, mock_db):

    feedback = DummyFeedback()

    response = save_feedback(feedback)

    assert response["message"] == "Feedback saved successfully"
    mock_db.assert_called_once()
    mock_file.assert_called_once()


@patch("app.services.feedback_service.save_feedback_db")
def test_save_feedback_db_failure(mock_db):

    mock_db.side_effect = Exception("DB error")

    feedback = DummyFeedback()

    try:
        save_feedback(feedback)
    except Exception as e:
        assert "DB error" in str(e)