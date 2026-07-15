from fastapi.testclient import TestClient

from main import app

# `with TestClient(app) as client:` は使わない。
# startupイベント（自律クローラー等の無限ループタスク）が動き出してしまうため、
# ここではlifespanを発火させない素のインスタンス化のみでルーティングを検証する。
client = TestClient(app)


def test_root_returns_ok():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
