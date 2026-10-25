from pathlib import Path
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

ROOT = Path(__file__).resolve().parent
INPUT = str(ROOT / "data" / "pune_demo_observations.csv")
OUTPUT = str(ROOT / "outputs" / "spark_batch")

def main():
    spark = (
        SparkSession.builder
        .appName("GreenPulsePuneBatch")
        .getOrCreate()
    )
    df = spark.read.option("header", True).option("inferSchema", True).csv(INPUT)

    # Basic quality checks and typed columns.
    df = (
        df.withColumn("observation_date", F.to_date("observation_date"))
          .withColumn("lst_celsius", F.col("lst_celsius").cast("double"))
          .withColumn("ndvi", F.col("ndvi").cast("double"))
          .withColumn("latitude", F.col("latitude").cast("double"))
          .withColumn("longitude", F.col("longitude").cast("double"))
          .dropna(subset=["zone_id", "observation_date", "lst_celsius", "ndvi", "latitude", "longitude"])
          .dropDuplicates(["zone_id", "observation_date"])
    )

    summary = (
        df.groupBy("zone_id", "zone_name")
          .agg(
              F.avg("latitude").alias("latitude"),
              F.avg("longitude").alias("longitude"),
              F.avg("lst_celsius").alias("mean_lst_c"),
              F.max("lst_celsius").alias("max_lst_c"),
              F.avg("ndvi").alias("mean_ndvi"),
              F.avg("ndbi").alias("mean_ndbi"),
              F.countDistinct("observation_date").alias("observation_count"),
          )
    )
    w = Window
    summary = summary.withColumn(
        "heat_score",
        F.when(F.max("mean_lst_c").over(w.partitionBy()) == F.min("mean_lst_c").over(w.partitionBy()), F.lit(0.5))
         .otherwise((F.col("mean_lst_c") - F.min("mean_lst_c").over(w.partitionBy())) /
                    (F.max("mean_lst_c").over(w.partitionBy()) - F.min("mean_lst_c").over(w.partitionBy())))
    ).withColumn(
        "vegetation_score",
        F.when(F.max("mean_ndvi").over(w.partitionBy()) == F.min("mean_ndvi").over(w.partitionBy()), F.lit(0.5))
         .otherwise((F.col("mean_ndvi") - F.min("mean_ndvi").over(w.partitionBy())) /
                    (F.max("mean_ndvi").over(w.partitionBy()) - F.min("mean_ndvi").over(w.partitionBy())))
    ).withColumn("priority_score", 0.5 * F.col("heat_score") + 0.5 * (1 - F.col("vegetation_score")))

    Path(OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    summary.write.mode("overwrite").parquet(OUTPUT)
    print(f"Processed rows: {df.count()}")
    print(f"Distinct zones: {summary.count()}")
    print(f"Saved Spark output to: {OUTPUT}")
    summary.orderBy(F.desc("priority_score")).show(20, truncate=False)
    spark.stop()

if __name__ == "__main__":
    main()
