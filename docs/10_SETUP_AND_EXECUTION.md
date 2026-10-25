# 10. Setup and execution

These instructions target Windows PowerShell and this repository layout. Package installation and application launch commands follow the checked-in manifests; external Docker/Spark commands require local tools and are not claimed as verified integration runs.

## Prerequisites

- Python and pip; the existing README recommends Python 3.10 or 3.11, but no `pyproject.toml` or lockfile pins a supported interpreter.
- MySQL server and the existing `greenpulse_pune` database/base summary table for database-backed pages.
- Optional Docker Desktop for the included Kafka container.
- Optional Java and a Spark installation compatible with the pinned PySpark version and Kafka connector.

The dependencies inspected in the active project environment were Streamlit 1.66.1, Pandas 2.3.3, NumPy 2.5.4, Plotly 6.9.0, PyDeck 0.9.3, scikit-learn 1.9.1, `kafka-python` 2.3.2, and PySpark 4.2.0. These are observed environment versions, not a lockfile.

## Create the environment and start the dashboard

```powershell
cd "C:\path\to\greenpulse_pune_demo"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

The browser normally opens at `http://localhost:8501`. If activation is blocked for the current shell, use:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Configure database access

Set non-secret connection values in the same PowerShell session. Enter the password securely:

```powershell
$env:MYSQL_HOST = "127.0.0.1"
$env:MYSQL_PORT = "3306"
$env:MYSQL_USER = "root"
$env:MYSQL_DATABASE = "greenpulse_pune"
$securePassword = Read-Host "MySQL password" -AsSecureString
$env:MYSQL_PASSWORD = [System.Net.NetworkCredential]::new("", $securePassword).Password
```

The app also supports values in local `.streamlit/secrets.toml`; never commit that local secrets file. The password reported as missing or denied should be resolved with the MySQL account's actual credential and grants, not by embedding it in source.

## Apply the optional ML migration

The existing base schema must already be present. From PowerShell with the MySQL command-line client installed:

```powershell
Get-Content -Raw .\database\migrations\001_environmental_ml.sql | mysql --host=127.0.0.1 --user=root --password greenpulse_pune
```

The client prompts for the password. The migration adds the observation-history, predictions, and recommendation tables; it does not create or alter `zone_environment_summary`.

## Optional Kafka replay

Install streaming Python dependencies and launch Kafka:

```powershell
pip install -r requirements-streaming.txt
docker compose up -d kafka
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic pune-environmental-observations --partitions 3 --replication-factor 1
```

In another terminal, activate the environment and run the replay:

```powershell
python kafka_producer.py
```

To use a prepared, independently verified CSV rather than the synthetic default, set its absolute path first:

```powershell
$env:GREENPULSE_DATASET_PATH = "C:\path\to\verified_observations.csv"
```

In a separate terminal with MySQL variables configured, run the Spark consumer:

```powershell
spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.2.0 spark_streaming.py
```

Connector coordinate compatibility with the locally installed Spark/Scala build needs verification. Keep producer, broker, and Spark in separate processes. Use `Ctrl+C` to stop the producer and Spark; use `docker compose down` to stop Kafka.

## Train and run ML

The legacy exploratory script can be run independently:

```powershell
python ml_analysis.py
```

It writes `outputs\zone_analysis.csv` and `outputs\model_metrics.json`; its random train/test split is not a chronological forecast evaluation. An optional Spark batch demonstration can be run with:

```powershell
spark-submit spark_batch.py
```

This batch script reads the bundled synthetic CSV and writes Parquet under `outputs\spark_batch`. It is separate from Kafka Structured Streaming.

For a synthetic classroom demo:

```powershell
python -m ml.train_model --demo
python -m ml.predict --demo
```

For the strict real-data mode:

```powershell
python -m ml.data_readiness
python -m ml.train_model
python -m ml.predict
```

Real mode requires reviewed non-demo history and can exit blocked until the readiness minima are met. Demo and real artifacts are kept separate.

## Tests and stop behavior

```powershell
python -m unittest tests.test_ml_pipeline -v
```

Stop each foreground process with `Ctrl+C`. If PowerShell contains a pasted program prompt or JSON response, clear the line and run only the actual command; terminal output is not executable input. See [test evidence](11_TESTING_AND_VALIDATION.md) and [the local-runtime diagram](diagrams/07_local_runtime_architecture.mmd).

**Figure 10.1.** Local process layout for browser, Streamlit, Python producer, Docker Kafka, Spark submission, MySQL, and project files. Open-Meteo is an optional outbound request. [Editable local-runtime diagram](diagrams/07_local_runtime_architecture.mmd).
