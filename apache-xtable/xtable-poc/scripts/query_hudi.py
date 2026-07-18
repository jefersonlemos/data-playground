from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("query-hudi")
    .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
    .getOrCreate()
)

df = spark.read.format("hudi").load("/lakehouse/hudi/sales")
df.createOrReplaceTempView("sales")

spark.sql("""
    SELECT region, COUNT(*) AS sale_count, ROUND(SUM(amount), 2) AS total_amount
    FROM sales
    GROUP BY region
    ORDER BY region
""").show(truncate=False)

spark.stop()
