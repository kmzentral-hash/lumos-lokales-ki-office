from fastapi.testclient import TestClient

from lumos_core.main import app

client = TestClient(app)


def test_inspect_table_data() -> None:
    csv_data = "Produkt,Menge,Preis\nStuhl,4,49.90\nTisch,2,199.00\nLampe,10,15.50"
    payload = {"csv_content": csv_data, "delimiter": ","}
    response = client.post("/api/v1/tables/inspect", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["row_count"] == 3
    assert data["column_count"] == 3
    assert data["headers"] == ["Produkt", "Menge", "Preis"]
    assert len(data["columns"]) == 3
    # Check numeric sum for Preis
    preis_col = next(c for c in data["columns"] if c["name"] == "Preis")
    assert preis_col["data_type"] == "numeric"
    assert preis_col["sum_value"] == 264.4


def test_analyze_table_data_sum_and_avg() -> None:
    csv_data = "Kunde,Umsatz\nFirma A,1200.50\nFirma B,3400.00\nFirma C,800.00"
    payload = {
        "csv_content": csv_data,
        "target_column": "Umsatz",
        "operation": "sum",
    }
    response = client.post("/api/v1/tables/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["result_value"] == 5400.5
    assert "5.400,50" in data["formatted_result"]
