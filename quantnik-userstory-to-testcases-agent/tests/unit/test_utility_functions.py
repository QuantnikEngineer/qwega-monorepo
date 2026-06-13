"""
Unit tests for utility functions in userstory2TestCasesAgent.py

Tests cover:
- get_scenario_type()
- _normalize_multiline()
- _retry_api_call()
"""
import pytest
from unittest.mock import MagicMock, patch
import json
import time


class TestGetScenarioType:
    """Tests for get_scenario_type() function."""
    
    def test_returns_list(self):
        """Test that function returns a list."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import get_scenario_type
            result = get_scenario_type()
            assert isinstance(result, list)
    
    def test_returns_all_expected_types(self, valid_scenario_types):
        """Test that all expected scenario types are returned."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import get_scenario_type
            result = get_scenario_type()
            assert len(result) == 11
            for expected_type in valid_scenario_types:
                assert expected_type in result
    
    def test_returns_functional_type(self):
        """Test that Functional type is included."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import get_scenario_type
            result = get_scenario_type()
            assert "Functional" in result
    
    def test_returns_non_functional_type(self):
        """Test that Non Functional type is included."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import get_scenario_type
            result = get_scenario_type()
            assert "Non Functional" in result
    
    def test_returns_boundary_negative_type(self):
        """Test that Boundary & Negative type is included."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import get_scenario_type
            result = get_scenario_type()
            assert "Boundary & Negative" in result
    
    def test_returns_gherkin_types(self):
        """Test that Gherkin types are included."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import get_scenario_type
            result = get_scenario_type()
            assert "Gherkin Functional" in result
            assert "Gherkin Boundary & Negative" in result
    
    def test_returns_ui_related_types(self):
        """Test that UI-related types are included."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import get_scenario_type
            result = get_scenario_type()
            assert "Buttons Enabled-Disabled" in result
            assert "Dropdown-Picklist" in result
    
    def test_returns_architecture_type(self):
        """Test that System Architecture type is included."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import get_scenario_type
            result = get_scenario_type()
            assert "System Architecture" in result
    
    def test_returns_combinatorial_type(self):
        """Test that Combinatorial type is included."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import get_scenario_type
            result = get_scenario_type()
            assert "Combinatorial" in result
    
    def test_returns_bug_related_type(self):
        """Test that Bug Related type is included."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import get_scenario_type
            result = get_scenario_type()
            assert "Bug Related" in result
    
    def test_returns_patch_related_type(self):
        """Test that Patch Related type is included."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import get_scenario_type
            result = get_scenario_type()
            assert "Patch Related" in result
    
    def test_no_duplicate_types(self):
        """Test that there are no duplicate scenario types."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import get_scenario_type
            result = get_scenario_type()
            assert len(result) == len(set(result))


class TestNormalizeMultiline:
    """Tests for _normalize_multiline() function."""
    
    def test_returns_none_for_none_input(self):
        """Test that None input returns None."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _normalize_multiline
            result = _normalize_multiline(None)
            assert result is None
    
    def test_normalizes_escaped_newlines(self):
        """Test that escaped newlines are converted to actual newlines."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _normalize_multiline
            result = _normalize_multiline("line1\\nline2")
            assert result == "line1\nline2"
    
    def test_normalizes_escaped_tabs(self):
        """Test that escaped tabs are converted to actual tabs."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _normalize_multiline
            result = _normalize_multiline("col1\\tcol2")
            assert result == "col1\tcol2"
    
    def test_normalizes_mixed_escapes(self):
        """Test that mixed escape sequences are normalized."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _normalize_multiline
            result = _normalize_multiline("line1\\nline2\\tcol2")
            assert result == "line1\nline2\tcol2"
    
    def test_handles_plain_text(self):
        """Test that plain text without escapes is returned as-is."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _normalize_multiline
            result = _normalize_multiline("plain text without escapes")
            assert result == "plain text without escapes"
    
    def test_handles_empty_string(self):
        """Test that empty string is handled correctly."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _normalize_multiline
            result = _normalize_multiline("")
            assert result == ""
    
    def test_handles_quoted_json_double_quotes(self):
        """Test that double-quoted JSON strings are parsed."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _normalize_multiline
            result = _normalize_multiline('"simple string"')
            assert result == "simple string"
    
    def test_handles_whitespace_only(self):
        """Test that whitespace-only strings are handled."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _normalize_multiline
            result = _normalize_multiline("   ")
            assert result == "   "
    
    def test_preserves_actual_newlines(self):
        """Test that actual newlines in input are preserved."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _normalize_multiline
            result = _normalize_multiline("line1\nline2")
            assert result == "line1\nline2"
    
    def test_handles_multiple_consecutive_escapes(self):
        """Test multiple consecutive escape sequences."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _normalize_multiline
            result = _normalize_multiline("a\\n\\n\\nb")
            assert result == "a\n\n\nb"


class TestRetryApiCall:
    """Tests for _retry_api_call() function."""
    
    def test_success_on_first_try(self):
        """Test successful execution on first attempt."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _retry_api_call
            
            mock_func = MagicMock(return_value="success")
            result = _retry_api_call(mock_func, max_retries=3, initial_delay=0.01)
            
            assert result == "success"
            assert mock_func.call_count == 1
    
    def test_retry_on_ssl_error(self):
        """Test retry on SSL error."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _retry_api_call
            
            mock_func = MagicMock()
            mock_func.side_effect = [Exception("SSL certificate verify failed"), "success"]
            
            result = _retry_api_call(mock_func, max_retries=3, initial_delay=0.01)
            
            assert result == "success"
            assert mock_func.call_count == 2
    
    def test_retry_on_connection_error(self):
        """Test retry on connection error."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _retry_api_call
            
            mock_func = MagicMock()
            mock_func.side_effect = [Exception("Connection refused"), "success"]
            
            result = _retry_api_call(mock_func, max_retries=3, initial_delay=0.01)
            
            assert result == "success"
            assert mock_func.call_count == 2
    
    def test_retry_on_timeout_error(self):
        """Test retry on timeout error."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _retry_api_call
            
            mock_func = MagicMock()
            mock_func.side_effect = [Exception("Request timeout"), "success"]
            
            result = _retry_api_call(mock_func, max_retries=3, initial_delay=0.01)
            
            assert result == "success"
            assert mock_func.call_count == 2
    
    def test_fail_after_max_retries(self):
        """Test failure after exhausting all retries."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _retry_api_call
            
            mock_func = MagicMock()
            mock_func.side_effect = Exception("SSL error persistent")
            
            with pytest.raises(Exception, match="SSL error persistent"):
                _retry_api_call(mock_func, max_retries=3, initial_delay=0.01)
            
            assert mock_func.call_count == 3
    
    def test_non_retryable_error_fails_immediately(self):
        """Test that non-retryable errors fail immediately."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _retry_api_call
            
            mock_func = MagicMock()
            mock_func.side_effect = ValueError("Invalid input")
            
            with pytest.raises(ValueError, match="Invalid input"):
                _retry_api_call(mock_func, max_retries=3, initial_delay=0.01)
            
            assert mock_func.call_count == 1
    
    def test_retry_on_max_retries_exceeded_error(self):
        """Test retry on 'Max retries exceeded' error."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _retry_api_call
            
            mock_func = MagicMock()
            mock_func.side_effect = [Exception("Max retries exceeded"), "success"]
            
            result = _retry_api_call(mock_func, max_retries=3, initial_delay=0.01)
            
            assert result == "success"
            assert mock_func.call_count == 2
    
    def test_retry_on_eof_error(self):
        """Test retry on EOF error."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _retry_api_call
            
            mock_func = MagicMock()
            mock_func.side_effect = [Exception("Unexpected EOF"), "success"]
            
            result = _retry_api_call(mock_func, max_retries=3, initial_delay=0.01)
            
            assert result == "success"
            assert mock_func.call_count == 2
    
    def test_retry_on_remote_disconnected(self):
        """Test retry on RemoteDisconnected error."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _retry_api_call
            
            mock_func = MagicMock()
            mock_func.side_effect = [Exception("RemoteDisconnected"), "success"]
            
            result = _retry_api_call(mock_func, max_retries=3, initial_delay=0.01)
            
            assert result == "success"
            assert mock_func.call_count == 2
    
    def test_retry_on_closed_connection(self):
        """Test retry on closed connection error."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _retry_api_call
            
            mock_func = MagicMock()
            mock_func.side_effect = [Exception("Connection closed unexpectedly"), "success"]
            
            result = _retry_api_call(mock_func, max_retries=3, initial_delay=0.01)
            
            assert result == "success"
    
    def test_retry_on_aborted_connection(self):
        """Test retry on aborted connection error."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _retry_api_call
            
            mock_func = MagicMock()
            mock_func.side_effect = [Exception("Connection aborted"), "success"]
            
            result = _retry_api_call(mock_func, max_retries=3, initial_delay=0.01)
            
            assert result == "success"
    
    def test_default_max_retries(self):
        """Test default max_retries value of 5."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.time.sleep'):
            from userstory2TestCasesAgent import _retry_api_call
            
            mock_func = MagicMock()
            mock_func.side_effect = Exception("SSL error")
            
            with pytest.raises(Exception):
                _retry_api_call(mock_func)
            
            assert mock_func.call_count == 5
    
    def test_multiple_retryable_errors_then_success(self):
        """Test multiple retryable errors followed by success."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            from userstory2TestCasesAgent import _retry_api_call
            
            mock_func = MagicMock()
            mock_func.side_effect = [
                Exception("SSL error"),
                Exception("Connection timeout"),
                "success"
            ]
            
            result = _retry_api_call(mock_func, max_retries=5, initial_delay=0.01)
            
            assert result == "success"
            assert mock_func.call_count == 3
