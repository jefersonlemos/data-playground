from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("create-hudi-sales")
    .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
    .getOrCreate()
)

data = [
    (1, "BR", "2026-07-01", 100.50),
    (2, "BR", "2026-07-01", 220.00),
    (3, "US", "2026-07-02", 80.25),
    (4, "US", "2026-07-02", 140.00),
    (5, "DE", "2026-07-03", 99.99),
]

df = spark.createDataFrame(data, ["sale_id", "region", "sale_date", "amount"])

table_path = "/lakehouse/hudi/sales"

(
    df.write.format("hudi")
    .option("hoodie.table.name", "sales")
    .option("hoodie.datasource.write.recordkey.field", "sale_id")
    .option("hoodie.datasource.write.precombine.field", "sale_date")
    .option("hoodie.datasource.write.partitionpath.field", "region")
    .option("hoodie.datasource.write.hive_style_partitioning", "true")
    .option("hoodie.datasource.write.table.type", "COPY_ON_WRITE")
    .mode("overwrite")
    .save(table_path)
)

spark.stop()
