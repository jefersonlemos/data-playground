from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("query-delta")
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    .getOrCreate()
)

df = spark.read.format("delta").load("/lakehouse/hudi/sales")
df.createOrReplaceTempView("sales")

spark.sql("""
    SELECT region, COUNT(*) AS sale_count, ROUND(SUM(amount), 2) AS total_amount
    FROM sales
    GROUP BY region
    ORDER BY region
""").show(truncate=False)

spark.stop()
