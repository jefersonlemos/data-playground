# Apache XTable Presentation

This markdown follows the current `slides.odp` structure. The ODP is the main presentation; this file is the readable outline, speaker-note source, and content checklist.

# 1. Title

## Slide content

Apache XTable

Metadata interoperability for Apache Hudi, Apache Iceberg, and Delta Lake

## Visual

- ODP uses the XTable logo/title visual.

# 2. Context: Problem statement

## Slide content

- Data warehouses made analytics reliable, but often kept data tied to one vendor.
- Data lakes made storage cheaper and open.
- Tools like Hudi, Iceberg, and Delta made data lakes easier to update and query safely.
- Different teams and engines adopted different formats.
- Converting formats created duplication, cost, and synchronization work.

## Visual

- `data-lake-specialized-tools.png`

## Speaker notes

Data architectures evolved because the old warehouse model did not fit every workload or every scale/cost profile. Data lakes solved part of the problem by using open storage and open file formats, especially Parquet.

But a folder of Parquet files is not a real table by itself. You still need a way to manage concurrent writes, schema changes, partitions, deletes, historical versions, and query planning. That is why Hudi, Iceberg, and Delta Lake exist.

- Different teams choose different table formats.
- Different engines and vendors support different formats better.
- Same Parquet files do not mean same table metadata.
- Without interoperability, teams either standardize too hard or duplicate/convert data.
- At scale this means storage cost, compute cost, freshness delay, and more pipelines to operate.

The real problem is table-level compatibility, not file-level compatibility. The data files may be Parquet, but Hudi, Iceberg, and Delta Lake describe table state differently.

# 3. Context: Problem statement

## Slide content

The problem is not storing the data.

The problem is making the same table readable across ecosystems without copying it.

## Speaker notes

Use this slide to make the core problem simple:

"We already have the data. The hard part is letting different tools read the same table without creating another copy."

Each format has its own metadata model for commits, snapshots, schemas, partitions, statistics, deletes, and history. A query engine that understands Iceberg does not automatically understand a Hudi table just because the files are Parquet.

# 4. Apache XTable: Introduction

## Slide content

- Apache XTable provides omni-directional interoperability across lakehouse table formats.
- It is NOT a new table format.
- It provides abstractions and tools for translating lakehouse table format metadata.
- It was formerly known as OneTable.
- Supported core table formats today: Hudi, Iceberg, Delta Lake.

## Visual

- `xtable-is-is-not-slide-04-v2.png`

## Speaker notes

XTable is best understood as a metadata interoperability layer with one authoritative source table.

It is not an ETL engine. It is not a storage format. It is not a distributed scheduler. It is not a complete bidirectional multi-writer database.

This distinction matters because it explains both the benefit and the limitations.

# 5. Apache XTable: How it solves the problem

## Slide content

- Hudi, Iceberg, and Delta all combine data files + table metadata.
- XTable reads the source table metadata.
- It creates equivalent target metadata using the target format APIs.
- Target metadata is written under the table base path:
  - `_delta_log/` for Delta
  - `metadata/` for Iceberg
  - `.hoodie/` for Hudi
- Query engines then read the same physical files through their preferred format.

## Visual

- ODP uses small metadata-directory visuals from `image-1.png` / `image-3.png`.

## Speaker notes

At a fundamental level, the formats share a similar shape: Parquet data files plus a metadata layer. XTable uses those commonalities.

The most important architectural point: it normally does not convert or rewrite the records. It translates metadata so the same files can be interpreted as another table format.

Good sentence to say:

"The conversion is not data-to-data. It is metadata-to-metadata."

# 6. Apache XTable: Architecture

## Slide content

The slide is visual-first. The diagram shows:

- source table metadata
- conversion controller
- neutral internal model
- target metadata for Iceberg, Delta, and Hudi

## Visual

- `xtable-architecture-slide-07-v2.png`

## Speaker notes

The important design choice is the neutral internal model. Without it, every format would need direct converters to every other format.

```text
Without neutral model: N * (N - 1) converters
With neutral model:    N sources + N targets
```

The controller coordinates extraction, sync mode, target creation, and optional catalog sync. Source and target logic are isolated behind adapters.

# 7. Apache XTable: Pros and Cons

## Slide content

| Topic | Pros | Cons |
|---|---|---|
| Data movement | Avoids copying or rewriting the data files in the normal path | It only translates metadata, so unsupported table semantics are not preserved |
| Read interoperability | Exposes one table as Hudi, Iceberg, or Delta for different engines | It is not a multi-writer layer; one format should remain authoritative |
| Large table sync | Incremental sync can make recurring updates much cheaper | Missing/unsafe history can force a full sync and increase runtime |
| Catalog operations | CatalogSync can reduce manual registration work across catalogs | Credentials, catalog configs, scheduling, and monitoring are still required |
| Feature support | Works well for common COW/read-optimized table views | MoR/log files, delete vectors, and some format-specific features are limited |

## Visual

- `xtable-pros-cons-slide-13-v3.png`

## Speaker notes

This is the main pros and cons slide. Keep it focused on XTable itself, not on competitors.

The positive story is simple: XTable can reduce data duplication and expose one physical dataset through multiple table-format ecosystems.

The careful story is also important: it is still metadata synchronization. It needs a source of truth, scheduled sync, operational ownership, and awareness of unsupported features.

Good sentence to say:

"XTable is useful because it avoids rewriting the data, but that also means it cannot translate every table-format semantic."

Plain-language limitation notes:

1. Table semantics: a special feature used by one format may not exist in another.
2. Multi-format writes: one format remains the source of truth; the others are generated read views.
3. Sync: XTable usually updates only what changed, but if it cannot safely find those changes, it must review the whole table again.
4. COW / read-optimized view: XTable works best with stable, completed files.
5. Advanced updates: MoR log files and delete vectors can be hard to share perfectly across formats.

# 8. Apache XTable: Trade-offs

## Slide content

| Trade-off | What you gain | What you accept |
|---|---|---|
| One sync, many formats | XTable can create Iceberg, Delta, or Hudi metadata from the same source table | The target formats may not update at exactly the same time if one sync succeeds and another fails |
| Easier to plug into pipelines | XTable can run as part of your existing Spark or data jobs | Your team still owns the schedule, retries, alerts, and recovery when something goes wrong |

## Visual

- `xtable-tradeoffs-slide-14-v1.png`

## Speaker notes

Keep this slide shorter than the pros/cons slide. It is here only to make the engineering trade-offs explicit.

If slide 7 is the practical pros/cons, slide 8 is the short technical summary:

- one sync can produce many formats, but the targets are not updated as one atomic transaction
- XTable fits into existing pipelines, but it does not replace scheduling, monitoring, and recovery

# 9. Apache XTable: Demo

## Slide content

Demo goal:

- Create or use one source table.
- Run XTable sync to generate target metadata.
- Show the generated metadata directories.
- Query the same data through another table format.

Suggested flow:

1. Show the source table files.
2. Run the XTable sync.
3. Show the new target metadata directories.
4. Query through the target format.

## Speaker notes

What the demo should prove:

- The data files are not duplicated.
- New metadata appears next to the same data.
- A query engine can use the generated metadata.

Important: do not overcomplicate the demo with too many engines. The demo should validate the core idea, not become an infrastructure tutorial.

Useful directory example:

```text
table/
  .hoodie/
  _delta_log/
  metadata/
  city=NYC/*.parquet
```

# Reference Notes

## Accuracy notes

- XTable is metadata sync, not a data copy or rewrite engine in the normal path.
- Full and incremental sync modes exist. Incremental is better for large tables, but XTable falls back to full if incremental sync cannot work safely.
- Catalog sync is separate from table-format sync. Creating `_delta_log/`, `metadata/`, or `.hoodie/` is not the same as registering the table in Glue, HMS, Unity Catalog, BigLake, or another catalog.
- Current limitations include Copy-on-Write or read-optimized views only. Hudi log files and Delta/Iceberg delete vectors are not captured by sync.
- One format should remain authoritative. XTable should not be presented as a magic bidirectional multi-writer database.
- Latest official release checked during this work: `0.3.0-incubating`.

## Useful links

- https://xtable.apache.org/
- https://xtable.apache.org/docs
- https://xtable.apache.org/docs/features-and-limitations/
- https://xtable.apache.org/docs/how-to/
- https://xtable.apache.org/docs/how-to-catalog-sync/
- https://xtable.apache.org/docs/demo/docker/
- https://xtable.apache.org/releases/downloads/
