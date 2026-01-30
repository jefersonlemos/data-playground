# Project description 

Must Create a Modern Data Pipeline with: 

1. Ingestion for 3 different data sources (Relational DB, File system and Traditional WS-*) (WebService/API) 
2. Modern Processing with Spark, Flink or Kafka Streams 
3. Data Lineage (chain “inspection“, tracing/tracking) 
4. Observability 
5. Pipelines must have at least 2 pipelines:
    1. Top Sales per City
    2. Top Salesman in the whole country 
6. The final Aggregated results mut be in a dedicated DB and API 
7. Restrictions: a. Python b. Red-Shift c. Hadoop

--- 

# Concepts 
## Data lineage
Is the ability to track the full journey of data, tracks what happened to the data.   
It is observability of the data itself, not just the infrastructure.

- Where the data came from
- How it was transformed
- Where it ended up being used

## CDC 
CDC (Change Data Capture) is a database design pattern that identifies, records, and streams row-level changes—inserts, updates, and deletes—made to a source database in real-time. It enables efficient, low-latency synchronization of data to downstream systems (data warehouses, data lakes, caches) without overloading the source database with full table scans. 

## KAFKA
- SINK -> Is the component that consumes data from Kafka and writes it to an external system.
    - Kafka ->  External system
- SOURCE -> brings data into kafka
    - External system -> Kafka

# Stack

## Data Lineage
- OpenLineage (https://openlineage.io/)
    - Open standard for lineage events
    - Works with:
    - Kafka
    - Flink
    - Spark
    - Airflow

- Marquez (https://marquezproject.ai/)
    - UI + backend for OpenLineage

## KAKFA

#### Configurations
- use ACK=all (leads and replicas needs to say OK)
- Define the Offset commit (short interval - less risk )
- Longer interval -> more performance -> more risk
- Make sure the destination is idempotent. (on kafka topics the duplication is normal and expected, the destination needs to know how deal with it)

### Kafka connectors
You can use self-managed Apache Kafka connectors to move data in and out of Kafka.   
![alt text](./resources/images/kafka_connectors.png)
https://docs.confluent.io/platform/current/connect/kafka_connectors.html

- Debezium CDC Connector
    - Debezium connectors capture changes to databases. Each Debezium connector establishes a connection to its source database, changes from one database table are written to a Kafka topic whose name corresponds to the table name
    - https://debezium.io/documentation/reference/stable/architecture.html
    - REAL CDC (log based)
    - Capture INSERT / DELETE / UPDATE
    - Is not a polling
- File system / object store
    - File stream connector 
        - The FileSource connector reads data from a file and sends it to Apache Kafka
        - https://docs.confluent.io/platform/current/connect/filestream_connector.html
        - https://docs.confluent.io/platform/current/connect/quickstart.html#write-file-data-with-kconnect
        - CSV
        - JSON
    - Amazon S3
        - Amazon S3 Source connector reads data exported to S3 and publishes it to an Apache Kafka topic
        - https://docs.confluent.io/kafka-connectors/s3-source
- WEB API
    - The Kafka Connect HTTP Source connector makes HTTP requests to an API, processes JSON responses, and produce those responses to Kafka.
    - https://docs.confluent.io/kafka-connectors/http-source