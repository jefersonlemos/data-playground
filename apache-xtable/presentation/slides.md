# Questions / things to check

Things that came to my mind

1. What about the performance of data translation? How good it is when transforming thousands of GBs of data?
2. How common are MoR tables / delete vectors in production? This matters because XTable does not support everything from these features.
3. Should the demo be only local docker or should I show an AWS/Athena path too?
4. Need to show generated metadata. This is probably the most convincing part of the presentation.
5. Need to avoid giving the idea that XTable is a magic bidirectional database. It is metadata sync.

Quick answers from research:

- Performance: XTable normally does not rewrite the data files, so it should be much cheaper than copying TBs of data. But the first run/full sync can still be expensive because it needs to inspect the table metadata/files/statistics. Incremental sync is the important performance story.
- If incremental sync cannot be done safely, XTable falls back to full sync. This is correct but can make runtime unpredictable.
- Catalog sync is separate from table-format sync. Generating `_delta_log/`, `metadata/`, or `.hoodie/` is not the same thing as registering the table in Glue, HMS, Unity, BigLake, etc.
- Athena note: XTable docs say Hudi target tables need Hudi 0.14.0, but Athena engine v3 currently supports Hudi 0.12.2, so Athena is not good to validate Hudi target tables. Iceberg/Delta targets are safer for Athena demo.
- Latest official release in XTable downloads is `0.3.0-incubating`. Do not present `0.4.0` as released unless checking again.

# Proposed presentation order

This is the order I think makes more sense after comparing `slides.md` with the ODP.

1. Title
2. Context: from warehouses to data lakes
3. Problem: table-format fragmentation
4. Why XTable is needed
5. What XTable is / is not
6. How XTable works
7. Architecture
8. Sync modes and performance - merge into slide 13
9. Catalog sync and ecosystem integrations - merge into slide 13
10. When to use XTable
11. Demo
12. Competitors / alternatives
13. Pros and cons, including sync/catalog trade-offs
14. Trade-offs
15. Conclusion

ODP changes to do later:

- Slide 2 should not show raw markdown (`##`) or empty bullets. Split it into two slides: context and problem.
- Slide 3 should explain the solution, not only say "Why XTable is needed".
- Slide 4 should explain XTable with one simple image and a short "is / is not" message.
- Slide 5 should have a simplified architecture diagram, not a screenshot of research notes.
- Remove or skip the standalone sync/performance and catalog/integrations slides.
- Merge the important sync/catalog points into the Pros and Cons slide, so the deck is lighter.
- Move competitors after the audience already understands what XTable does.
- Keep the demo before competitors or after limitations depending on timing. I prefer before competitors, because the demo makes the rest more concrete.

# 1. Title

## Slide content

Apache XTable

Metadata interoperability for Apache Hudi, Apache Iceberg, and Delta Lake
 

# 2. Context: Problem statement

## Slide content

- Data warehouses made analytics reliable, but often kept data tied to one vendor.
- Data lakes made storage cheaper and open.
- Tools like Hudi, Iceberg, and Delta made data lakes easier to update and query safely.
- Parquet became a common physical file format for analytical data.
- Different teams and engines adopted different formats
- Converting formats created duplication, cost, and synchronization work
- The problem is not storing the data. The problem is making the same table readable across ecosystems without copying it."


## Speaker notes

Data architectures evolved because the old warehouse model did not fit every workload or every scale/cost profile. Data lakes solved part of the problem by using open storage and open file formats, especially Parquet.

But a folder of Parquet files is not a real table by itself. You still need a way to manage concurrent writes, schema changes, partitions, deletes, historical versions, and query planning. That is why Hudi, Iceberg, and Delta Lake exist.

- Different teams choose different table formats.
- Different engines and vendors support different formats better.
- Same Parquet files do not mean same table metadata.
- Without interoperability, teams either standardize too hard or duplicate/convert data.
- At scale this means storage cost, compute cost, freshness delay, and more pipelines to operate.

The real problem is table-level compatibility, not file-level compatibility. The data files may be Parquet, but Hudi, Iceberg, and Delta Lake describe table state differently.

Each format has its own metadata model for commits, snapshots, schemas, partitions, statistics, deletes, and history. So a query engine that understands Iceberg does not automatically understand a Hudi table just because the files are Parquet.

## What to add in the ODP

- This should be its own slide, not mixed with the history slide.
- A good visual:
  - Same data files in the middle
  - Hudi / Iceberg / Delta metadata around it
  - Engines around those metadata formats

# X. Solving the problem

## Slide content

- The need is not another table format.
- The need is to make one physical dataset readable through multiple table-format ecosystems.
- Apache XTable translates metadata from one source format into one or more target formats.
- The physical data files stay in place.
- One format remains authoritative; the other formats are synchronized views.

## Speaker notes

XTable's core idea is simple: keep one copy of the data, but generate the metadata needed by other table formats.

So if the source table is Hudi, XTable can generate Iceberg metadata and Delta log metadata that point to the same physical files. Consumers can then read through the format their engine supports best.

This does not mean every feature is interchangeable. It also does not mean all formats should write independently to the same files.


# 3. Apache XTable - Introduction

## Slide content

- Apache XTable provides omni-directional interoperability across lakehouse table formats.
- It is NOT a new table format.
- It provides abstractions and tools for translating lakehouse table format metadata.
- It was formerly known as OneTable.
- Supported core table formats today: Hudi, Iceberg, Delta Lake.

## Speaker notes

XTable is best understood as a metadata interoperability layer with one authoritative source table.

It is not an ETL engine.
It is not a storage format.
It is not a distributed scheduler.
It is not a complete bidirectional multi-writer database.

This distinction matters because it explains both the benefit and the limitations.

## What to add in the ODP

- Add a small "is / is not" block:
  - Is: metadata translator
  - Is not: new format, data copy engine, multi-writer coordination layer

# 4. How XTable solves the problem

## Slide content

- Hudi, Iceberg, and Delta all combine data files + table metadata.
- XTable reads the source table metadata.
- It creates equivalent target metadata using the target format APIs.
- Target metadata is written under the table base path:
  - `_delta_log/` for Delta
  - `metadata/` for Iceberg
  - `.hoodie/` for Hudi
- Query engines then read the same physical files through their preferred format.

## Speaker notes

At a fundamental level, the formats share a similar shape: Parquet data files plus a metadata layer. XTable uses those commonalities.

The most important architectural point: it normally does not convert or rewrite the records. It translates metadata so the same files can be interpreted as another table format.

Good sentence to say:

"The conversion is not data-to-data. It is metadata-to-metadata."

## What to add in the ODP

- Show before/after:
  - before: `.hoodie/` + Parquet files
  - after: `.hoodie/` + `metadata/` + `_delta_log/` + same Parquet files
- Add a tiny example:

```text
spark.read.format("iceberg").load("path/to/table")
spark.read.format("delta").load("path/to/table")
spark.read.format("hudi").load("path/to/table")
```

# 5. Architecture

## Slide content

```text
CLI / REST service
      |
      v
ConversionController
      |
      +--> Source adapter
      |       reads source table metadata
      |
      +--> Neutral internal model
      |       schema + partitions + files + stats + commit state
      |
      +--> Target adapters
              write Iceberg / Delta / Hudi metadata
```

## Speaker notes

The important design choice is the neutral internal model. Without it, every format would need direct converters to every other format.

```text
Without neutral model: N * (N - 1) converters
With neutral model:    N sources + N targets
```

The controller coordinates extraction, sync mode, target creation, and optional catalog sync. Source and target logic are isolated behind adapters.

## What to add in the ODP

- Do not use `image-4.png` as-is. It is too much like a screenshot from notes.
- `image-2.png` and `image-3.png` are useful references, but the final slide should be redrawn with larger text.
- Keep this slide conceptual, not code-level.

# 8. Sync modes and performance - merge into slide 13

## Slide content moved

Do not keep this as a standalone slide in the simplified version.

Keep only the key message for slide 13:

- XTable can use incremental sync, so regular syncs do not need to rebuild everything.
- If incremental sync is not safe, XTable falls back to full sync.
- This is good for correctness, but it can make runtime more expensive/unpredictable.
- Sync is not magic freshness; the target metadata updates when the sync job runs.

## Speaker notes

This is where I should answer the "thousands of GBs" question.

The good part:

- It does not copy/rewrite TBs of Parquet data in the normal path.
- Incremental sync should be much cheaper than full conversion because it only handles new commits.

The careful part:

- The first sync still needs a snapshot of the table.
- Full fallback can be expensive for huge tables/object stores.
- Column statistics and metadata extraction can still cost time.
- If table cleaning/retention removed history needed for incremental sync, XTable chooses correctness and falls back to full.

## What to add in the ODP

- Remove this standalone slide or keep it only as backup.
- The simplified version uses one row in slide 13:
  - `Sync` / `Incremental sync keeps regular metadata work smaller` / `Target metadata can lag, and full fallback can be expensive`

# 9. Catalog sync and integrations - merge into slide 13

## Slide content moved

Do not keep this as a standalone slide in the simplified version.

Keep only the key message for slide 13:

- Table-format sync creates the target metadata files.
- Catalog sync registers or updates those tables in external catalogs.
- This reduces manual registration work.
- It still needs catalog configuration, credentials, scheduler, and monitoring.

## Speaker notes

This is a second fragmentation problem. Even if the table metadata exists, consumers often discover/query tables through catalogs.

Generating `metadata/` or `_delta_log/` does not necessarily register the table in Glue, HMS, Unity Catalog, or another catalog. XTable separates these concerns:

- TableFormatSync: create the table-format metadata
- CatalogSync: register/sync table metadata across catalogs

## What to add in the ODP

- Remove this standalone slide or keep it only as backup.
- The simplified version uses one row in slide 13:
  - `Catalogs` / `CatalogSync can register/update target tables` / `Catalogs, credentials, and monitoring are still operational work`

# 10. When to use XTable

## Slide content

Use XTable when:

- You already have data in Hudi, Iceberg, or Delta.
- Another team/tool needs a different table format.
- You want one physical copy of the data.
- You want to avoid rewrite-heavy conversion pipelines.
- You accept one authoritative writer/source format.
- You can operate periodic or continuous metadata sync.

Do not use XTable when:

- You need every format-specific feature to be semantically identical.
- Multiple engines need to write independently through different formats.
- Your tables depend on unsupported MoR/log/delete-vector behavior.
- You want a complete job orchestration platform.

## Speaker notes

Good framing:

"XTable is useful when the organization is heterogeneous but the data should not be duplicated."

It is strongest at read interoperability. It is not trying to replace the table formats themselves.

## What to add in the ODP

- This can be a decision slide.
- Use two columns: "Good fit" and "Bad fit".

# 11. Demo

## Slide content

Demo goal:

- Create or use one source table.
- Run XTable sync to generate target metadata.
- Show the generated metadata directories.
- Query the same data through another table format.

Best demo path:

1. Use the official Docker demo if time is short.
2. Show local files before/after sync.
3. Show one query through the source format and one through target format.
4. If using AWS, prefer Iceberg/Delta target for Athena validation.

## Speaker notes

What I want to prove in the demo:

- The data files are not duplicated.
- New metadata appears next to the same data.
- A query engine can use the generated metadata.

Important: do not overcomplicate the demo with too many engines. The demo should validate the core idea, not become an infrastructure tutorial.

## What to add in the ODP

- Keep demo slide as a checklist.
- Add one screenshot of generated directories:

```text
table/
  .hoodie/
  _delta_log/
  metadata/
  city=NYC/*.parquet
```

- Add a second screenshot/query output only if it is clean.

# 12. Competitors / alternatives

## Slide content

| Tool / approach | What it solves | Main difference from XTable |
|---|---|---|
| **Apache XTable** | Makes one physical dataset readable as multiple table formats | Neutral metadata interoperability layer across Hudi, Iceberg, and Delta |
| **Delta Lake UniForm** | Lets Iceberg/Hudi clients read a Delta table with one copy of the data | Closest alternative, but Delta is always the source of truth; Iceberg/Hudi are read-only |
| **Trino Lakehouse connector** | Lets one query engine query and write Hudi, Iceberg, Delta, and Hive tables | One query interface; does not translate table metadata or make one table appear as every format |
| **Apache Iceberg migration** | Moves or snapshots an existing table into Iceberg, sometimes without copying the files | A migration toward Iceberg, not ongoing multi-format interoperability |
| **ETL / CDC replication pipelines** | Read one format and write another, keeping separate tables synchronized | The traditional option: more pipelines, possible extra storage, compute, and freshness delay |

## Speaker notes

The closest direct alternative is Delta Lake UniForm. The other rows solve an adjacent problem, not exactly the same problem.

If the organization is all-in on Delta, UniForm may be a simpler choice. It generates Iceberg/Hudi metadata after Delta writes, but Delta remains the source of truth and external Iceberg/Hudi clients are read-only.

If the organization has mixed source formats or wants a neutral interoperability layer, XTable is more general.

Trino is useful if the main need is one SQL engine that can read different existing formats. It does not replace XTable because it does not create translated metadata for other engines.

Iceberg migration is useful when the final decision is "we are moving to Iceberg." It is not a long-term multi-format sync solution.

ETL/CDC is the traditional solution: create and maintain copies. It can be the right choice when the target table needs transformations or full format-specific behaviour.

Important: Hudi, Iceberg, and Delta Lake are not competitors to XTable. They are the table formats that XTable connects.

Useful sentence to say:

"UniForm is the closest alternative when Delta Lake is already the source of truth. XTable is broader because it is designed for interoperability across formats, not only from Delta."

### Official research links

- Delta Lake UniForm: <https://docs.delta.io/delta-uniform/>
- Trino Lakehouse connector: <https://trino.io/docs/current/connector/lakehouse.html>
- Apache Iceberg table migration: <https://iceberg.apache.org/docs/latest/table-migration/>
- AWS Glue data lake frameworks: <https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-datalake-native-frameworks.html>

## What to add in the ODP

- Keep this after architecture and sync, so the audience already understands what XTable does.
- Use the 5-row comparison table above.
- Make the XTable and UniForm rows visually stronger; the other three are adjacent approaches, not direct competitors.
- Add a small footnote: `Hudi, Iceberg, and Delta Lake are table formats, not XTable competitors.`

# 13. Pros and cons

## Slide content

| Topic | Pros | Cons |
|---|---|---|
| Data movement | Avoids copying or rewriting the data files in the normal path | It only translates metadata, so unsupported table semantics are not preserved |
| Read interoperability | Exposes one table as Hudi, Iceberg, or Delta for different engines | It is not a multi-writer layer; one format should remain authoritative |
| Large table sync | Incremental sync can make recurring updates much cheaper | Missing/unsafe history can force a full sync and increase runtime |
| Catalog operations | CatalogSync can reduce manual registration work across catalogs | Credentials, catalog configs, scheduling, and monitoring are still required |
| Feature support | Works well for common COW/read-optimized table views | MoR/log files, delete vectors, and some format-specific features are limited |

## Speaker notes

This is the main pros and cons slide. Keep it focused on XTable itself, not on competitors.

The positive story is simple: XTable can reduce data duplication and expose one physical dataset through multiple table-format ecosystems.

The careful story is also important: it is still metadata synchronization. It needs a source of truth, scheduled sync, operational ownership, and awareness of unsupported features.

Good sentence to say:

"XTable is useful because it avoids rewriting the data, but that also means it cannot translate every table-format semantic."

### Plain-language explanation for the limitations

1. **Table semantics:** XTable can share the same data between formats, but a special feature used by one format may not exist in another.
2. **Multi-format writes:** One format remains the source of truth; the others are generated read views.
3. **Sync:** XTable usually updates only what changed. If it cannot safely find those changes, it must review the whole table again.
4. **COW / read-optimized view:** Copy-on-Write (COW) stores data as complete files that are replaced when something changes. A read-optimized view reads only those completed files, ignoring temporary change files. This makes reading simpler and faster, though very recent changes may not appear until they are merged into the main files. XTable works best with these stable, completed files.
5. **Advanced updates:** Merge-on-Read (MoR) keeps recent changes separately and combines them with the main data during reading. Delete vectors are notes that say “do not show this row” without immediately changing the original file. These approaches can make updates faster, but formats handle them differently, so XTable cannot always share them perfectly.

## What to add in the ODP

- Replace the old pros/cons placeholder with this table.
- Use 5 rows only.
- Columns should be `Topic`, `Pros`, and `Cons`.
- Merge the previous sync slide and catalog slide into the `Large table sync` and `Catalog operations` rows.
- Use a visual table, not two long bullet columns.

# 14. Trade-offs

## Slide content

| Trade-off | What you gain | What you accept |
|---|---|---|
| One sync, many formats | XTable can create Iceberg, Delta, or Hudi metadata from the same source table | The target formats may not update at exactly the same time if one sync succeeds and another fails |
| Easier to plug into pipelines | XTable can run as part of your existing Spark or data jobs | Your team still owns the schedule, retries, alerts, and recovery when something goes wrong |

## Speaker notes

Keep this slide shorter than the pros/cons slide. It is here only to make the engineering trade-offs explicit.

If slide 13 is the practical pros/cons, slide 14 is the short technical summary:

- one sync can produce many formats, but the targets are not updated as one atomic transaction
- XTable fits into existing pipelines, but it does not replace scheduling, monitoring, and recovery

## What to add in the ODP

- Use this as a smaller follow-up slide.
- Do not spend much time here; the focus should remain slide 13.

# 15. Conclusion

## Slide content

Apache XTable is a metadata interoperability layer.

It helps expose one physical dataset through multiple table-format ecosystems without rewriting the data files.

Best fit:

- mixed lakehouse environments
- multiple engines/vendors
- one authoritative source table
- read interoperability

Main caution:

- it is not full semantic equivalence
- it is not independent multi-writer
- unsupported table features still matter

## Speaker notes

Closing sentence:

"XTable is not trying to hide the differences between Hudi, Iceberg, and Delta. It gives us a practical bridge when those differences exist in the same organization."

# Appendix: useful details for presentation

## Supported formats / status

- Current core formats: Apache Hudi, Apache Iceberg, Delta Lake.
- Apache XTable is incubating at the ASF and was renamed from OneTable.
- Incubation started on 2024-02-11 according to Apache Incubator.
- Latest official release listed in XTable downloads: `0.3.0-incubating`.
- Release 0.3.0 added CatalogSync interfaces, Glue/HMS sync, continuous sync using `RunSync`, restore/rollback support across all three formats, and more table-format sync improvements.

## Integrations that are worth mentioning

Official docs include:

- Catalogs: HMS, AWS Glue, Unity Catalog, BigLake Metastore
- Query engines/platforms: Athena, Redshift Spectrum, Spark, BigQuery, Fabric, Presto, Snowflake, StarRocks, Trino
- Docker demo

Potential talk examples:

- Hudi ingestion + Iceberg query in Snowflake
- Hudi/Iceberg source + Delta target for Databricks Unity Catalog
- Glue catalog + Athena for query validation
- Background conversion with AWS Lambda or scheduled Airflow/MWAA

## Accuracy notes

- XTable docs say metadata is persisted under `_delta_log` for Delta, `metadata` for Iceberg, and `.hoodie` for Hudi.
- Docs say full and incremental sync modes exist. Incremental is more lightweight and better for large tables, but XTable falls back to full if incremental cannot work properly.
- Docs say TableFormatSync includes data files plus column stats and partition metadata, source schema updates reflected in target metadata, and target metadata maintenance.
- Docs say CatalogSync can continuously/incrementally sync metadata across catalogs and currently documents HMS/AWS Glue as supported, with Unity, Apache Polaris, Apache Gravitino, and DataHub mentioned as future work in the features page.
- Docs say only Copy-on-Write or Read-Optimized views are currently supported. Hudi log files and Delta/Iceberg delete vectors are not captured by sync.
- Docs say Hudi target reads require Hudi 0.14.0 and some settings like `hoodie.metadata.enable=true` and hive style partitioning where applicable.
- Docs say generated columns from Delta source are not synced to target schema, with limited support for partitioning on generated columns.
- Official Athena integration page says Athena engine v3 supports Hudi 0.12.2, so Hudi target validation in Athena will not work for the Hudi 0.14.0 requirement.

# Sources and further reading

Official XTable:

- https://xtable.apache.org/
- https://xtable.apache.org/docs
- https://xtable.apache.org/docs/features-and-limitations/
- https://xtable.apache.org/docs/how-to/
- https://xtable.apache.org/docs/how-to-catalog-sync/
- https://xtable.apache.org/docs/athena/
- https://xtable.apache.org/docs/demo/docker/
- https://xtable.apache.org/releases/downloads/
- https://xtable.apache.org/releases/release-0.3.0-incubating/
- https://xtable.apache.org/blog/
- https://xtable.apache.org/blog/archive/
- https://incubator.apache.org/clutch/xtable.html

Useful external references:

- https://docs.delta.io/delta-uniform/
- https://aws.amazon.com/blogs/big-data/run-apache-xtable-in-aws-lambda-for-background-conversion-of-open-table-formats/
- https://aws.amazon.com/blogs/big-data/run-apache-xtable-on-amazon-mwaa-to-translate-open-table-formats/
- https://docs.onehouse.ai/product/external-integrations/catalogs/sync-troubleshooting/
