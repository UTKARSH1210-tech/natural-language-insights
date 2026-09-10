from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_csv_upload(tmp_path, monkeypatch):
    """
    A valid CSV upload should return 202 Accepted.
    """

    # The application uses relative paths such as "data/".
    # Create that directory inside pytest's temporary directory.
    monkeypatch.chdir(tmp_path)

    data_dir = Path("data")
    data_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    response = client.post(
        "/datasets",
        files={
            "file": (
                "sales.csv",
                b"product,quantity,revenue\n"
                b"A,2,10\n"
                b"B,3,20\n",
                "text/csv",
            )
        },
    )

    # Helpful if the test fails again.
    if response.status_code != 202:
        print("UPLOAD RESPONSE:", response.text)

    assert response.status_code == 202

    body = response.json()

    assert "job_id" in body
    assert "dataset_id" in body
    assert body["filename"] == "sales.csv"
    assert body["status"] == "queued"
    assert body["size_bytes"] > 0


def test_non_csv_rejected():
    """
    Non-CSV files should be rejected with HTTP 400.
    """

    response = client.post(
        "/datasets",
        files={
            "file": (
                "sales.txt",
                b"hello",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400

    body = response.json()

    assert body["detail"]["code"] == "INVALID_FILE_TYPE"