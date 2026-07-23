# Apache XTable architecture and conversion workflow

This report is based on Apache XTable commit [`4daec279`](https://github.com/apache/incubator-xtable/tree/4daec2795e6ec1234f0d0c8aa05aadee0780b714), dated July 8, 2026.

The most important architectural point is that XTable does **not normally convert or rewrite the underlying records**. It translates table-format metadata so the same physical data files can be interpreted as Hudi, Iceberg, or Delta tables. The [official XTable tutorial](https://xtable.apache.org/docs/how-to/) confirms that this happens without copying or moving the underlying files.

## 1. Architecture and system design

“System design” is the broader description of how XTable operates, while “architecture” describes the components implementing that design. Both are relevant.

XTable uses an adapter-based metadata translation architecture:

```text
                      CLI / REST service
                            |
                            v
                  ConversionController
                            |
             +--------------+--------------+
             |                             |
             v                             v
    Source-format adapter           Target-format adapters
    HudiConversionSource            IcebergConversionTarget
                                    DeltaConversionTarget
             |                             ^
             v                             |
      Neutral internal model --------------+
   schema + partitions + files + stats
             + commit state
```

The central architectural decision is a neutral internal representation:

```text
Hudi metadata
     | extract
     v
InternalTable / InternalSnapshot / InternalFilesDiff
     | translate
     v
Iceberg metadata, Delta log, or Hudi metadata
```

### 1.1 Entry points

- The bundled CLI reads YAML and constructs `SourceTable`, `TargetTable`, and `ConversionConfig`: [`RunSync.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-utilities/src/main/java/org/apache/xtable/utilities/RunSync.java#L120-L186).
- Continuous mode reruns the sync on a scheduled loop: [`RunSync.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-utilities/src/main/java/org/apache/xtable/utilities/RunSync.java#L257-L280).
- A Quarkus REST endpoint exists at `POST /v1/conversion/table`: [`ConversionResource.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-service/src/main/java/org/apache/xtable/service/ConversionResource.java#L32-L44).

### 1.2 Orchestrator

`ConversionController` coordinates extraction, full versus incremental selection, target creation, and optional catalog synchronization: [`ConversionController.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/conversion/ConversionController.java#L61-L108).

### 1.3 Source adapters

A `ConversionSource` understands one source format and exposes:

- Current table state
- Current snapshot
- Commit backlog
- Per-commit changes
- Whether incremental recovery is still safe

Hudi's implementation is [`HudiConversionSource.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/hudi/HudiConversionSource.java).

### 1.4 Neutral internal model

The format-independent model includes:

- `InternalTable`: schema, partition specification, base path, and latest commit
- `InternalDataFile`: physical path, size, format, partition values, and column statistics
- `InternalSnapshot`: table state plus its complete file inventory
- `InternalFilesDiff`: files added and removed by a commit

See [`InternalTable.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-api/src/main/java/org/apache/xtable/model/InternalTable.java#L31-L55) and [`InternalDataFile.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-api/src/main/java/org/apache/xtable/model/storage/InternalDataFile.java#L35-L55).

### 1.5 Target adapters

Every target implements `ConversionTarget`, whose lifecycle includes:

```java
beginSync(table);
syncMetadata(metadata);
syncSchema(schema);
syncPartitionSpec(partitions);
syncFilesForSnapshot(files); // or syncFilesForDiff(diff)
completeSync();
```

The interface is defined in [`ConversionTarget.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-api/src/main/java/org/apache/xtable/spi/sync/ConversionTarget.java#L35-L104). Implementations are discovered through Java's `ServiceLoader`: [`ConversionTargetFactory.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/conversion/ConversionTargetFactory.java#L84-L96).

### 1.6 Optional catalog synchronization

Table-format conversion and catalog registration are separate concerns. After generating target-format metadata, XTable can register or refresh the table in supported external catalogs. This is coordinated by `syncTableAcrossCatalogs`: [`ConversionController.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/conversion/ConversionController.java#L114-L159).

## 2. Hudi-to-Iceberg/Delta conversion steps

### 1. Read configuration and construct the conversion request

A typical configuration is:

```yaml
sourceFormat: HUDI
targetFormats:
  - ICEBERG
  - DELTA
datasets:
  - tableBasePath: s3://bucket/people
    tableName: people
    partitionSpec: city:VALUE
```

`RunSync` turns this into a `SourceTable`, multiple `TargetTable` objects, and an incremental `ConversionConfig`: [`RunSync.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-utilities/src/main/java/org/apache/xtable/utilities/RunSync.java#L158-L186).

```java
ConversionConfig.builder()
    .sourceTable(sourceTable)
    .targetTables(targetTables)
    .syncMode(SyncMode.INCREMENTAL)
    .build();
```

### 2. Open the Hudi table and active timeline

`HudiConversionSourceProvider` creates a `HoodieTableMetaClient` using the configured base path and Hadoop filesystem configuration: [`HudiConversionSourceProvider.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/hudi/HudiConversionSourceProvider.java#L37-L53).

```java
HoodieTableMetaClient.builder()
    .setBasePath(sourceTable.getBasePath())
    .setLoadActiveTimelineOnLoad(true)
    .build();
```

For Merge-on-Read tables, XTable warns that only base files are synchronized. Hudi log files are not included.

### 3. Initialize one target adapter per requested format

The controller excludes the source format itself and creates an adapter for every other target: [`ConversionController.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/conversion/ConversionController.java#L176-L197).

```text
HUDI source
 |-- IcebergConversionTarget
 `-- DeltaConversionTarget
```

Each target adapter loads existing target metadata, if present, and retrieves XTable's previous synchronization state.

### 4. Decide between full and incremental synchronization

XTable reads `XTABLE_METADATA` from each target. It contains state similar to:

```json
{
  "lastInstantSynced": "...",
  "instantsToConsiderForNextSync": [],
  "sourceTableFormat": "HUDI",
  "sourceIdentifier": "..."
}
```

The state is defined in [`TableSyncMetadata.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-api/src/main/java/org/apache/xtable/model/metadata/TableSyncMetadata.java#L37-L80).

XTable chooses a full snapshot when:

- The target has never been synchronized.
- Full mode was explicitly requested.
- The relevant Hudi commit is no longer available.
- Hudi cleaning may have removed files needed to reconstruct incremental changes.

The decision is made in [`ConversionController.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/conversion/ConversionController.java#L254-L278), with fallback logic at [lines 326–351](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/conversion/ConversionController.java#L326-L351).

The Hudi-specific safety check considers timeline retention and cleaner metadata: [`HudiConversionSource.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/hudi/HudiConversionSource.java#L164-L214).

### 5. Extract Hudi schema and partition structure

For the selected Hudi commit, XTable:

1. Resolves its Avro schema.
2. Converts it into `InternalSchema`.
3. Derives the partition fields.
4. Identifies Hudi record-key fields.
5. Produces an `InternalTable`.

This happens in [`HudiTableExtractor.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/hudi/HudiTableExtractor.java#L60-L91).

```java
return InternalTable.builder()
    .tableFormat(TableFormat.HUDI)
    .readSchema(canonicalSchema)
    .partitioningFields(partitionFields)
    .latestCommitTime(...)
    .build();
```

Hudi partition semantics may require explicit configuration:

```yaml
partitionSpec: event_time:DAY:yyyy-MM-dd,region:VALUE
```

This is needed because directory names do not always express the original transform semantics.

### 6. Extract the complete snapshot or per-commit file differences

For a **full sync**, XTable:

- Finds every Hudi partition.
- Uses Hudi's filesystem view to find the latest base files.
- Extracts partition values from paths.
- Groups files by partition.

See [`HudiDataFileExtractor.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/hudi/HudiDataFileExtractor.java#L115-L126) and [lines 346–365](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/hudi/HudiDataFileExtractor.java#L346-L365).

For an **incremental sync**, it examines each Hudi timeline action and constructs added and removed file lists for:

- `commit` and `deltacommit`
- `replacecommit`
- `rollback`
- `restore`
- Maintenance actions that do not affect base files

See [`HudiDataFileExtractor.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/hudi/HudiDataFileExtractor.java#L148-L252).

A Hudi update usually becomes:

```text
old Parquet base file -> REMOVE
new Parquet base file -> ADD
```

### 7. Attach file and column statistics

Each `InternalDataFile` receives information such as:

```text
physical path
file size
record count
partition values
column min/max/null counts
```

XTable first uses Hudi's metadata-table column statistics. If statistics are missing, it reads Parquet footers as a fallback: [`HudiFileStatsExtractor.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/hudi/HudiFileStatsExtractor.java#L95-L112) and [lines 168–187](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/hudi/HudiFileStatsExtractor.java#L168-L187).

This allows target query engines to retain file-pruning capabilities.

### 8. Apply each source change through a common target lifecycle

For every target, XTable executes:

```java
beginSync(tableState);
syncMetadata(latestState);
syncSchema(schema);
syncPartitionSpec(partitions);
syncFilesForSnapshot(files); // or syncFilesForDiff(diff)
completeSync();
```

This ordering is implemented in [`TableFormatSync.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-api/src/main/java/org/apache/xtable/spi/sync/TableFormatSync.java#L153-L187).

Incremental changes are applied commit by commit. Once a target fails, later changes for that target are skipped during that run: [`TableFormatSync.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-api/src/main/java/org/apache/xtable/spi/sync/TableFormatSync.java#L99-L139).

### 9. For an Iceberg target, write metadata referencing the Hudi files

The Iceberg adapter:

1. Creates or loads an Iceberg table.
2. Converts and synchronizes the schema.
3. Synchronizes the partition specification.
4. Converts each internal file into an Iceberg `DataFile`.
5. Commits an Iceberg overwrite and snapshot.

See [`IcebergConversionTarget.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/iceberg/IcebergConversionTarget.java#L151-L169).

The critical operation is:

```java
DataFiles.builder(partitionSpec)
    .withPath(dataFile.getPhysicalPath())
    .withFileSizeInBytes(dataFile.getFileSizeBytes())
    .withMetrics(...)
    .build();
```

See [`IcebergDataFileUpdatesSync.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/iceberg/IcebergDataFileUpdatesSync.java#L119-L133).

The path is still the original Hudi-created file. Iceberg manifests and metadata JSON are new, but the Parquet file is not rewritten.

### 10. For a Delta target, write Delta actions referencing the Hudi files

The Delta adapter converts internal files into `AddFile` and `RemoveFile` actions: [`DeltaDataFileUpdatesExtractor.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/delta/DeltaDataFileUpdatesExtractor.java#L88-L128).

```java
new AddFile(
    relativeOriginalFilePath,
    partitionValues,
    fileSize,
    modificationTime,
    true,
    columnStats,
    null,
    null);
```

It then commits:

- Table schema
- Partition columns
- Add/remove actions
- XTable synchronization metadata
- Delta protocol and retention properties

See [`DeltaConversionTarget.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/delta/DeltaConversionTarget.java#L312-L371).

The resulting `_delta_log` points to the same files represented by Hudi.

### 11. Persist progress and perform metadata maintenance

XTable writes `XTABLE_METADATA` into the target so the next run can continue incrementally.

It also performs target-specific maintenance:

- Iceberg: expire old snapshots, deleting only files under the Iceberg `metadata` directory.
- Delta: configure transaction-log retention.
- Hudi targets: manage unreferenced metadata entries.

For Iceberg, see [`IcebergConversionTarget.java`](https://github.com/apache/incubator-xtable/blob/4daec2795e6ec1234f0d0c8aa05aadee0780b714/xtable-core/src/main/java/org/apache/xtable/iceberg/IcebergConversionTarget.java#L289-L308).

### 12. Optionally register the table in external catalogs

Generating `metadata/` or `_delta_log/` does not necessarily register the table in Glue, HMS, or another catalog. Catalog synchronization is a subsequent, optional step.

The project currently documents HMS and AWS Glue support, with other catalogs listed as future work in the [official features and limitations](https://xtable.apache.org/docs/features-and-limitations/).

## 3. Pros and cons

### Pros

1. **No data duplication**

   XTable normally writes metadata rather than copying or rewriting table data. This is faster and substantially cheaper for large tables.

2. **Cross-engine interoperability**

   A Hudi-ingested dataset can be exposed through Iceberg or Delta metadata to engines that support those formats better.

3. **Format-neutral core**

   The internal model prevents every format from needing direct converters to every other format:

   ```text
   Without neutral model: N * (N - 1) converters
   With neutral model:    N sources + N targets
   ```

4. **Incremental synchronization**

   After the initial snapshot, XTable can process only new source commits, reducing filesystem listing and metadata-generation work.

5. **Safe fallback**

   When Hudi's retained timeline is insufficient, XTable detects that and performs a complete snapshot sync instead of applying an incomplete delta.

6. **Preserves useful statistics**

   Partition values, record counts, and column statistics are translated so target engines can perform metadata and file pruning.

7. **Extensible adapter interfaces**

   New targets implement `ConversionTarget`; source-specific logic remains isolated behind `ConversionSource`.

8. **Per-target failure isolation**

   Multiple targets can be synchronized in one run, and one target's error does not necessarily prevent other formats from completing.

### Cons

1. **It is not complete semantic conversion**

   Only metadata representable by the internal model and target format is translated. Format-specific features can be lost.

2. **No complete Hudi Merge-on-Read conversion**

   Merge-on-Read tables expose only their base-file/read-optimized state. Uncompacted changes in Hudi log files will not appear in the target view.

3. **Delete-vector limitations**

   Delta and Iceberg deletion vectors are not currently represented. The documentation limits support to Copy-on-Write or read-optimized views. See the [official limitations](https://xtable.apache.org/docs/features-and-limitations/).

4. **One authoritative writer is effectively required**

   The source format should remain authoritative. Independently writing through Hudi, Iceberg, and Delta metadata over the same files risks divergent histories and conflicting lifecycle operations.

5. **Partition interpretation may require manual configuration**

   Hudi partition transforms sometimes require `partitionSpec` because directory paths do not retain enough information to infer the transformation reliably.

6. **Schema edge cases are difficult**

   Field IDs, list encoding, generated columns, map-key evolution, requiredness, and format-specific type rules do not map perfectly.

7. **Metadata synchronization is asynchronous**

   Target formats lag behind the source until the next XTable execution. Continuous mode narrows this window but does not make the formats one atomic transaction.

8. **Full fallback can be expensive**

   When incremental history is unavailable, XTable must list and compare the entire table. This becomes costly for large tables or object stores.

9. **Operational complexity remains**

   Operators still need storage credentials, compatible format libraries, retention settings, catalog registration, monitoring, and scheduling.

10. **The REST service is relatively thin**

    The REST layer delegates directly to the same controller. It is not a complete job-control platform with durable queues, rich history, distributed scheduling, or a management UI.

## 4. Trade-offs

1. **Metadata-only speed versus semantic completeness**

   Reusing existing files avoids expensive rewrites, but XTable cannot translate information that exists only in unsupported logs, delete vectors, indexes, or format-specific metadata.

2. **Neutral model simplicity versus lowest-common-denominator behavior**

   `InternalTable` makes the system extensible, but any format feature that cannot fit the shared model needs an extension or is omitted.

3. **Incremental performance versus retained-history dependency**

   Incremental sync is efficient only while the source timeline and cleaned files contain enough history. More aggressive Hudi cleaning saves storage but causes more full XTable synchronizations.

4. **Multiple readable formats versus single-writer discipline**

   Several query engines can read the same data through their preferred format, but allowing all of them to write makes ownership and conflict resolution ambiguous.

5. **Shared physical files versus coordinated lifecycle management**

   Storage use is minimized, but vacuuming or deleting a file through one format can break every other format whose metadata still references it. Data-file deletion policies must therefore be controlled centrally.

6. **Preserved commit history versus exact historical equivalence**

   XTable creates corresponding target commits and records source identifiers, but timestamps, snapshot IDs, and transaction boundaries are target-specific. Histories are analogous, not identical.

7. **Automatic fallback versus unpredictable runtime**

   Falling back to a full snapshot favors correctness, but a normally small incremental job can suddenly become a large filesystem scan.

8. **Multi-target fan-out versus no cross-target atomicity**

   Hudi-to-Iceberg may succeed while Hudi-to-Delta fails. This improves availability but means consumers can temporarily see different source versions depending on their selected format.

9. **Target-native metadata versus compatibility constraints**

   Native Iceberg manifests and Delta actions provide broad engine compatibility, but their schemas, partition semantics, field IDs, and protocols must remain within what both the original files and target readers support.

## Conclusion

XTable is best understood as a **metadata interoperability layer with one authoritative source table**, not as an ETL engine or a bidirectional multi-writer database.
