# Apache XTable PoC

This repository demonstrates Apache XTable interoperability by creating one Apache Hudi table and generating Delta Lake and Apache Iceberg metadata for the same physical Parquet files.

The PoC produces this layout:

```text
lakehouse/hudi/sales/.hoodie       # Hudi metadata
lakehouse/hudi/sales/_delta_log    # Delta Lake metadata
lakehouse/hudi/sales/metadata      # Iceberg metadata
lakehouse/hudi/sales/region=BR     # Shared Parquet data
lakehouse/hudi/sales/region=DE     # Shared Parquet data
lakehouse/hudi/sales/region=US     # Shared Parquet data
```

## Run the PoC

Run the following steps from the root of this repository.

1. Enter the PoC directory.

   ```bash
   cd xtable-poc
   ```

2. Confirm Docker access and prepare the lakehouse directory.

   ```bash
   docker ps
   mkdir -p lakehouse
   chmod 0777 lakehouse
   ```

3. Build Apache XTable.

   The source code is already located in `incubator-xtable`.

   ```bash
   cd incubator-xtable
   ./mvnw install -DskipTests
   cd ..
   ```

4. Create the source Hudi table.

   This runs [`create_hudi_sales.py`](xtable-poc/scripts/create_hudi_sales.py) with Spark 3.5.1 and Hudi 0.15.0.

   ```bash
   docker run --rm \
     -e HOME=/tmp \
     -e HADOOP_USER_NAME=spark \
     -v "$PWD/lakehouse:/lakehouse" \
     -v "$PWD/scripts:/scripts:ro" \
     apache/spark:3.5.1 \
     /opt/spark/bin/spark-submit \
     --conf spark.jars.ivy=/tmp/.ivy2 \
     --packages org.apache.hudi:hudi-spark3.5-bundle_2.12:0.15.0 \
     /scripts/create_hudi_sales.py
   ```

5. Verify the Hudi table.

   ```bash
   find lakehouse/hudi/sales -maxdepth 3 -type d | sort
   find lakehouse/hudi/sales -name '*.parquet' | sort
   ```

   Before the XTable conversion, the table contains Hudi metadata and three data partitions:

   ```text
   lakehouse/hudi/sales/.hoodie
   lakehouse/hudi/sales/region=BR
   lakehouse/hudi/sales/region=DE
   lakehouse/hudi/sales/region=US
   ```

6. Select the Apache XTable command-line JAR.

   XTable builds multiple bundled JARs. This PoC must use the executable `xtable-utilities` JAR.

   ```bash
   XTABLE_JAR="$(find incubator-xtable/xtable-utilities/target \
     -name 'xtable-utilities_*-bundled.jar' -print -quit)"

   test -n "$XTABLE_JAR" || {
     echo "XTable utilities bundled jar was not found. Build XTable first." >&2
     exit 1
   }
   ```

7. Run Apache XTable to generate Delta and Iceberg metadata.

   XTable reads [`sales.yml`](xtable-poc/xtable-config/sales.yml), uses Hudi as the source format, and creates metadata for the Delta and Iceberg target formats.

   ```bash
   docker run --rm \
     -v "$PWD/lakehouse:/lakehouse" \
     -v "$PWD/xtable-config:/xtable-config:ro" \
     -v "$PWD/$XTABLE_JAR:/xtable.jar:ro" \
     eclipse-temurin:11 \
     java -jar /xtable.jar \
     --datasetConfig /xtable-config/sales.yml
   ```

   Successful output includes:

   ```text
   Sync is successful for the following formats ICEBERG,DELTA
   ```

8. Verify the XTable conversion.

   ```bash
   find lakehouse/hudi/sales -maxdepth 2 -type d | sort
   ```

   Expected result:

   ```text
   lakehouse/hudi/sales/.hoodie
   lakehouse/hudi/sales/_delta_log
   lakehouse/hudi/sales/metadata
   lakehouse/hudi/sales/region=BR
   lakehouse/hudi/sales/region=DE
   lakehouse/hudi/sales/region=US
   ```

Apache XTable only creates the target table-format metadata in this PoC. The Delta, Iceberg, and Hudi views reference the same Parquet data files; the dataset is not copied three times.

## Detailed article

See [Apache XTable PoC blog](apache-xtable-poc-blog.html) for the complete explanation, metadata inspection, query comparison, and presentation notes.
