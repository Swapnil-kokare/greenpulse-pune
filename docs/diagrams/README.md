# Diagram index

The `.mmd` files are editable Mermaid source, not screenshots of a deployed cloud system. Render them in a Mermaid-compatible Markdown viewer or GitHub. All components shown are local project components or explicitly labelled optional external API calls.

| Figure | Source | Caption and interpretation |
|---|---|---|
| 3.1 | [01_system_architecture.mmd](01_system_architecture.mmd) | **Overall system architecture.** Shows the synthetic CSV replay, optional Open-Meteo estimates, local Kafka/Spark processing, MySQL summary/history storage, ML paths, and Streamlit presentation. |
| 4.1 | [02_end_to_end_data_flow.mmd](02_end_to_end_data_flow.mmd) | **End-to-end data flow.** Shows parsing, required-value filtering, summary aggregation, conditional history upsert, and dashboard/ML consumers. |
| 5.1 | [03_kafka_spark_sequence.mmd](03_kafka_spark_sequence.mmd) | **Kafka/Spark sequence.** Shows producer-to-broker events, Spark batch work, and MySQL write acknowledgement; the optional history sink is separate. |
| 7.1 | [04_ml_training_inference.mmd](04_ml_training_inference.mmd) | **ML training and inference.** Contrasts strict real-data eligibility with explicit synthetic demo mode and distinct artifacts/persistence. |
| 6.1 | [05_database_er.mmd](05_database_er.mmd) | **Database ER diagram.** Shows the inspected summary entity and migration entities. The only declared foreign key connects an optional recommendation to a prediction; unique composite keys are described in the source comment and [database chapter](../06_DATABASE_DESIGN.md). |
| 9.1 | [06_dashboard_user_workflow.mmd](06_dashboard_user_workflow.mmd) | **Dashboard user workflow.** Shows page navigation, API/data availability branches, ML readiness, and refresh behavior. |
| 10.1 | [07_local_runtime_architecture.mmd](07_local_runtime_architecture.mmd) | **Local runtime architecture.** Shows browser, local processes, Docker Kafka, MySQL, files, and optional outbound provider requests. |
