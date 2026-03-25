import pytest
from unittest.mock import patch, MagicMock
from gcspub.sdk import gcp
from gcspub.sdk.exceptions import ConfigurationError

def test_public_enable_friendly_error_on_drs():
    """Verify that a DRS block returns the detailed friendly error with remediation paths."""
    with patch('gcspub.sdk.gcp._run_gcloud') as mock_run:
        # Simulate gcloud failure with Domain Restricted Sharing error
        mock_run.side_effect = Exception("Domain Restricted Sharing violation")
        
        with pytest.raises(ConfigurationError) as excinfo:
            gcp.public_enable(repair=False)
            
        assert "Domain Restricted Sharing (DRS) Policy Blocked Public Access" in str(excinfo.value)
        assert "MANUAL (Google Cloud Console)" in str(excinfo.value)
        assert "DIRECT (gcloud CLI)" in str(excinfo.value)
        assert "gcspub public enable --repair-org-policies" in str(excinfo.value)

def test_public_enable_repair_trigger():
    """Verify that repair=True triggers the repair logic."""
    with patch('gcspub.sdk.gcp._run_gcloud') as mock_run:
        with patch('gcspub.sdk.gcp._repair_org_policies') as mock_repair:
            # Simulate initial DRS failure
            mock_run.side_effect = [
                None, # update PAP
                None, # update UBLA
                Exception("Domain Restricted Sharing violation"), # iam binding fail
                None, # iam binding success after repair
            ]
            mock_repair.return_value = True
            
            result = gcp.public_enable(repair=True)
            assert result.get("success") is True
            assert result.get("repaired") is True
            mock_repair.assert_called_once()
