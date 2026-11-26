import pytest
from fastapi.testclient import TestClient

from backend.app.api.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.mark.integration
def test_dashboard_overview_all_time(client):
    response = client.get("/api/dashboard/overview?period=all_time")
    assert response.status_code == 200
    data = response.json()

    assert data["period"] == "all_time"
    assert data["period_label"] == "All Time"
    assert "date_range" in data

    # Verify verified baseline figures
    kpis = data["kpis"]
    assert kpis["total_orders"]["value"] == 50000
    assert abs(kpis["total_revenue"]["value"] - 4745475661.63) < 1.0
    assert abs(kpis["average_order_value"]["value"] - 94909.51) < 1.0
    assert kpis["total_customers"]["value"] == 10000
    assert abs(kpis["return_rate"]["value"] - 7.17) < 0.1

    # Verify sections
    assert len(data["revenue_analytics"]["timeline"]) >= 12
    assert len(data["category_sales"]) == 6
    assert len(data["top_products"]) == 5
    assert len(data["campaign_performance"]["top_campaigns"]) == 5
    assert len(data["customer_insights"]["segments"]) == 5
    assert len(data["business_insights"]) == 5
    assert data["operational_health"]["shipments"]["total_shipments"] == 50000


@pytest.mark.integration
def test_dashboard_overview_periods(client):
    for period in ["this_year", "last_90_days", "last_30_days", "last_7_days"]:
        response = client.get(f"/api/dashboard/overview?period={period}")
        assert response.status_code == 200
        data = response.json()
        assert data["period"] == period
        assert data["kpis"]["total_orders"]["value"] > 0
        assert data["kpis"]["total_revenue"]["value"] > 0
