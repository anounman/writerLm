import pytest
from unittest.mock import patch, MagicMock

from web.backend.llm_util import parse_user_prompt

def test_llm_invalid_json_fallback():
    db = MagicMock()
    user = MagicMock()
    
    with patch("web.backend.llm_util.get_or_create_user_config") as mock_config, \
         patch("web.backend.llm_util._api_keys_by_provider") as mock_keys, \
         patch("web.backend.llm_util.build_openai_client") as mock_client:
        
        mock_config.return_value.settings = {"llm_provider": "google"}
        mock_keys.return_value = {"google": "fake_key"}
        
        # Mock client to return invalid JSON
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "This is not valid JSON."
        mock_client.return_value.chat.completions.create.return_value = mock_response
        
        # Should not raise exception
        result = parse_user_prompt(db, user, "A book about programming in Python.")
        
        # Should fallback to safe values
        assert result["topic"] == "A book about programming in Python"
        assert result["code_density"] == "medium"
        assert result["book_type"] == "conceptual_guide"

def test_llm_invalid_json_fallback_non_tech():
    db = MagicMock()
    user = MagicMock()
    
    with patch("web.backend.llm_util.get_or_create_user_config") as mock_config, \
         patch("web.backend.llm_util._api_keys_by_provider") as mock_keys, \
         patch("web.backend.llm_util.build_openai_client") as mock_client:
        
        mock_config.return_value.settings = {"llm_provider": "google"}
        mock_keys.return_value = {"google": "fake_key"}
        
        # Mock client to return invalid JSON
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "INVALID"
        mock_client.return_value.chat.completions.create.return_value = mock_response
        
        result = parse_user_prompt(db, user, "A book about cooking.")
        assert result["code_density"] == "none"

