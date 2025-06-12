from unittest.mock import MagicMock, patch

import pytest

from tails.main import health_live, health_ready, scalar_html


@pytest.mark.anyio
async def test_health_live():
    response = await health_live()
    assert response == {"status": "live"}


@pytest.mark.anyio
async def test_health_ready_success():
    with patch("tails.main.get_s3_client") as mock_get_s3_client:
        mock_s3 = MagicMock()
        mock_get_s3_client.return_value = mock_s3
        mock_s3.head_bucket.return_value = None
        response = await health_ready()
        assert response["status"] == "healthy"
        assert response["s3_connection"] == "ok"


@pytest.mark.anyio
async def test_health_ready_failure():
    with patch("tails.main.get_s3_client") as mock_get_s3_client:
        mock_s3 = MagicMock()
        mock_get_s3_client.return_value = mock_s3
        mock_s3.head_bucket.side_effect = Exception("fail")
        response = await health_ready()
        assert response["status"] == "unhealthy"
        assert "fail" in response["error"]


@pytest.mark.anyio
async def test_docs():
    response = await scalar_html()
    assert response.status_code == 200
    assert "html" in response.body.decode("utf-8")
