# Databricks notebook source
# DBTITLE 1,Install dependencies
%pip install dbldatagen --quiet

# COMMAND ----------

# DBTITLE 1,Restart Python
dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Import dbldatagen
import dbldatagen as dg

# COMMAND ----------

# DBTITLE 1,Setup generation utilities
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import *

spark.conf.set("spark.sql.ansi.enabled", "false")
CATALOG = "aw_serverless_stable_catalog"
SCHEMA = "aibi_member_claims"
VERSION_SUFFIX = "_v2"

def fqn(table):
    return f"{CATALOG}.{SCHEMA}.{table}{VERSION_SUFFIX}"

def base_df(rows, name):
    gen = dg.DataGenerator(spark, name=name, rows=rows, seedColumnName="_id")
    gen = gen.withColumn("_dummy", IntegerType(), minValue=1, maxValue=rows, percentNulls=0.0)
    df = gen.build()
    w = Window.orderBy(F.monotonically_increasing_id())
    return df.withColumn("_rn", F.row_number().over(w)).select("_rn")

def weighted(values, weights, seed):
    r = F.rand(seed)
    running = 0.0
    expr = F.lit(values[-1])
    for v, wt in reversed(list(zip(values[:-1], weights[:-1]))):
        running = sum(weights[:values.index(v)+1])
        expr = F.when(r <= running, F.lit(v)).otherwise(expr)
    return expr

def weighted2(values, weights, seed):
    r = F.rand(seed)
    cum = []
    s = 0.0
    for w in weights:
        s += w
        cum.append(s)
    expr = F.lit(values[-1])
    for i in range(len(values)-2, -1, -1):
        expr = F.when(r <= cum[i], F.lit(values[i])).otherwise(expr)
    return expr

def parent_sample_col(parent_table, parent_key, fk_type, rows):
    vals = [r[0] for r in spark.table(fqn(parent_table)).select(parent_key).distinct().orderBy(parent_key).collect()]
    assert len(vals) > 1, f"Parent {parent_table}.{parent_key} has insufficient diversity"
    arr = F.array([F.lit(v) for v in vals])
    col = F.element_at(arr, ((F.col("_rn") - 1) % len(vals) + 1).cast("int"))
    if isinstance(fk_type, LongType):
        return col.cast("bigint")
    if isinstance(fk_type, IntegerType):
        return col.cast("int")
    return col

def default_col(cname, dtype, table, rows):
    lc = cname.lower()
    if isinstance(dtype, LongType):
        return F.col("_rn").cast("bigint")
    if isinstance(dtype, IntegerType):
        if lc.endswith("line_nbr") or lc.endswith("seq"):
            return (((F.col("_rn") - 1) % 10) + 1).cast("int")
        if "hour" in lc:
            return (F.col("_rn") % 24).cast("int")
        return (F.col("_rn") % max(rows, 2)).cast("int")
    if isinstance(dtype, BooleanType):
        return (F.rand(abs(hash(cname)) % 10000) > 0.15)
    if isinstance(dtype, DateType):
        return F.date_add(F.lit("2021-01-01").cast("date"), (F.col("_rn") % 1200).cast("int"))
    if isinstance(dtype, TimestampType):
        d = F.date_add(F.lit("2021-01-01").cast("date"), (F.col("_rn") % 1200).cast("int"))
        return F.to_timestamp(d)
    if isinstance(dtype, DecimalType):
        maxv = 950.0 if dtype.precision <= 9 else 100000.0
        if any(x in lc for x in ["paid", "allowed", "net"]):
            maxv = 6000.0
        if "billed" in lc:
            maxv = 8500.0
        if any(x in lc for x in ["deduct", "copay", "coinsurance", "not_covered"]):
            maxv = 900.0
        return F.round(F.rand(abs(hash(cname)) % 10000) * F.lit(maxv), min(dtype.scale, 2)).cast(dtype)
    prefix = ''.join([p[0] for p in table.split('_')])[:3].upper()
    if "name" in lc and "full" not in lc:
        return F.concat(F.lit("Name "), F.col("_rn").cast("string"))
    if "full_name" in lc or "member_name" in lc:
        return F.concat(F.lit("Member "), F.col("_rn").cast("string"))
    if "email" in lc:
        return F.concat(F.lit("member"), F.col("_rn").cast("string"), F.lit("@example.org"))
    if "phone" in lc or lc.endswith("nbr"):
        return F.concat(F.lit("555"), F.lpad((F.col("_rn") % 10000000).cast("string"), 7, "0"))
    if "zip" in lc:
        return F.lpad((F.lit(10000) + (F.col("_rn") % 89999)).cast("string"), 5, "0")
    if "hash" in lc:
        return F.sha2(F.concat(F.lit(table), F.col("_rn").cast("string")), 256)
    return F.concat(F.lit(prefix + "-"), F.lpad(F.col("_rn").cast("string"), 8, "0"))

def build_table(table, rows, pk_cols, domains, fks):
    schema = spark.table(fqn(table)).schema
    df = base_df(rows, table)
    for field in schema.fields:
        cname = field.name
        dtype = field.dataType
        if cname in fks:
            ptab, pkey = fks[cname]
            df = df.withColumn(cname, parent_sample_col(ptab, pkey, dtype, rows))
        elif cname in pk_cols:
            if isinstance(dtype, (LongType, IntegerType)):
                df = df.withColumn(cname, F.col("_rn").cast(dtype))
            else:
                prefix = table[:3].upper() + "-"
                df = df.withColumn(cname, F.concat(F.lit(prefix), F.lpad(F.col("_rn").cast("string"), 10, "0")))
        elif cname in domains:
            vals, wts = domains[cname]
            df = df.withColumn(cname, weighted2(vals, wts, abs(hash(table + cname)) % 10000).cast(dtype))
        else:
            df = df.withColumn(cname, default_col(cname, dtype, table, rows))
    df = df.select([f.name for f in schema.fields])
    total = df.count()
    if pk_cols:
        key_expr = F.concat_ws("||", *[F.col(c).cast("string") for c in pk_cols])
        distinct = df.select(key_expr.alias("k")).distinct().count()
        assert distinct == total, f"{table} composite PK not unique: {distinct}/{total}"
    for fk in fks:
        assert df.select(fk).distinct().count() > 1, f"{table}.{fk} FK diversity failure"
    for dc in domains:
        samples = [str(r[0]) for r in df.select(dc).distinct().limit(20).collect()]
        assert not any(s.startswith("val_") or s in ["A","B","C"] for s in samples), f"Generic domain values in {table}.{dc}"
    df.write.format("delta").mode("append").saveAsTable(fqn(table))
    print(f"Wrote {total} rows to {fqn(table)}")

lob_vals = (["COMMERCIAL", "MEDICARE", "MEDICAID", "TRICARE", "EXCHANGE"], [0.38,0.24,0.22,0.10,0.06])
state_vals = (["CA", "TX", "FL", "NY", "PA", "IL", "OH", "GA"], [0.18,0.15,0.13,0.12,0.10,0.09,0.08,0.07])
source_vals = (["FACETS", "QNXT", "EPIC", "AMISYS"], [0.45,0.30,0.15,0.10])
claim_type_vals = (["Institutional", "Professional", "Pharmacy", "Dental", "Vision"], [0.30,0.35,0.15,0.12,0.08])

# COMMAND ----------

# DBTITLE 1,Generate parent dimensions
build_table("dim_member", 500, ["member_sk"], {
    "mbr_race": (["White", "Black or African American", "Asian", "Hispanic", "Native American", "Other", "Unknown"], [0.48,0.18,0.08,0.18,0.02,0.04,0.02]),
    "mbr_sex": (["Female", "Male", "Unknown"], [0.52,0.47,0.01]),
    "mbr_ethnicity": (["Not Hispanic or Latino", "Hispanic or Latino", "Unknown"], [0.72,0.24,0.04]),
    "mbr_marital_status": (["Single", "Married", "Divorced", "Widowed", "Unknown"], [0.34,0.46,0.10,0.06,0.04]),
    "mbr_line_of_business": lob_vals,
    "mbr_state": state_vals,
    "mbr_relationship_type": (["Subscriber", "Spouse", "Child", "Domestic Partner", "Other Dependent"], [0.55,0.18,0.22,0.03,0.02]),
    "source_system_code": source_vals,
    "source_system_name": (["Facets Claims", "QNXT Core", "Epic Eligibility", "Amisys Advance"], [0.45,0.30,0.15,0.10])
}, {})

build_table("dim_provider", 200, ["provider_sk"], {
    "source_system": (["NPPES", "Credentialing", "ProviderMaster", "ClaimsSystem"], [0.40,0.25,0.25,0.10])
}, {})

# COMMAND ----------

# DBTITLE 1,Generate dependent dimensions and bridges
build_table("dim_address", 500, ["address_key"], {
    "entity_type_key": (["MEMBER", "PROVIDER", "FACILITY"], [0.70,0.20,0.10]),
    "address_type_code": (["HOME", "MAILING", "BILLING", "SERVICE"], [0.60,0.25,0.10,0.05]),
    "state": state_vals,
    "country_code": (["US", "PR", "GU"], [0.96,0.03,0.01]),
    "source_system_code": source_vals,
    "source_system_name": (["Facets Claims", "QNXT Core", "Epic Eligibility", "Amisys Advance"], [0.45,0.30,0.15,0.10])
}, {"entity_dimension_key": ("dim_member", "member_sk")})

build_table("dim_member_identifier", 800, ["mbr_identifier_sk"], {
    "id_type": (["Member ID", "Subscriber ID", "Medicare Beneficiary ID", "Medicaid ID", "Employee ID"], [0.35,0.25,0.18,0.17,0.05]),
    "source_system_code": source_vals,
    "source_system_name": (["Facets Claims", "QNXT Core", "Epic Eligibility", "Amisys Advance"], [0.45,0.30,0.15,0.10])
}, {"member_sk": ("dim_member", "member_sk")})

build_table("dim_member_history", 1000, ["mbr_history_sk"], {
    "mbr_race": (["White", "Black or African American", "Asian", "Hispanic", "Native American", "Other", "Unknown"], [0.48,0.18,0.08,0.18,0.02,0.04,0.02]),
    "mbr_sex": (["Female", "Male", "Unknown"], [0.52,0.47,0.01]),
    "mbr_ethnicity": (["Not Hispanic or Latino", "Hispanic or Latino", "Unknown"], [0.72,0.24,0.04]),
    "mbr_line_of_business": lob_vals,
    "mbr_state": state_vals,
    "source_system_code": source_vals,
    "source_system_name": (["Facets Claims", "QNXT Core", "Epic Eligibility", "Amisys Advance"], [0.45,0.30,0.15,0.10])
}, {"member_sk": ("dim_member", "member_sk")})

# COMMAND ----------

# DBTITLE 1,Generate fact tables
build_table("fact_member_enrollment", 1500, ["enrollment_sk"], {
    "source_system": (["FACETS", "QNXT", "EPIC", "AMISYS"], [0.45,0.30,0.15,0.10]),
    "mbr_enr_status": (["Active", "Terminated", "Pending", "Suspended", "COBRA"], [0.72,0.16,0.06,0.04,0.02]),
    "mbr_enr_line_of_business": lob_vals,
    "mbr_enr_group_name": (["Acme Manufacturing", "Metro Schools", "State Employees", "Health Exchange Silver", "Senior Advantage"], [0.28,0.22,0.20,0.18,0.12]),
    "mbr_enr_subgroup_name": (["North Region", "South Region", "Retiree", "Active Employee", "Dependent"], [0.25,0.22,0.18,0.25,0.10]),
    "mbr_enr_termination_reason": (["Voluntary Termination", "Non Payment", "Group Cancelled", "Moved Out of Area", "Coverage Replaced"], [0.35,0.20,0.15,0.15,0.15]),
    "id_type": (["Member ID", "Subscriber ID", "Medicare Beneficiary ID", "Medicaid ID"], [0.40,0.25,0.20,0.15])
}, {"member_sk": ("dim_member", "member_sk")})

build_table("fact_claim_header", 3000, ["clm_header_sk"], {
    "clm_claim_type": claim_type_vals,
    "clm_bill_type": (["Inpatient Hospital", "Outpatient Hospital", "Skilled Nursing", "Home Health", "Clinic"], [0.18,0.32,0.08,0.07,0.35]),
    "clm_admission_type": (["Emergency", "Urgent", "Elective", "Newborn", "Trauma"], [0.30,0.22,0.38,0.06,0.04]),
    "clm_admission_source": (["Physician Referral", "Emergency Room", "Transfer", "Clinic Referral", "Court/Law Enforcement"], [0.34,0.30,0.14,0.18,0.04]),
    "clm_line_of_business": lob_vals,
    "clm_submitting_provider_type": (["Primary Care", "Specialist", "Hospital", "Pharmacy", "Ancillary"], [0.30,0.26,0.20,0.14,0.10]),
    "clm_service_type_code": (["Medical Care", "Surgery", "Consultation", "Diagnostic", "Emergency"], [0.32,0.16,0.20,0.22,0.10]),
    "clm_cob_type": (["Primary", "Secondary", "Tertiary"], [0.76,0.20,0.04]),
    "clm_claim_timely_filing": (["Timely", "Late", "Exception Approved"], [0.86,0.10,0.04]),
    "clm_accept_assignment_indicator": (["Accepted", "Not Accepted", "Unknown"], [0.78,0.18,0.04]),
    "source_system_code": source_vals,
    "source_system_name": (["Facets Claims", "QNXT Core", "Epic Eligibility", "Amisys Advance"], [0.45,0.30,0.15,0.10])
}, {"clm_member_sk": ("dim_member", "member_sk")})

build_table("fact_claim_detail", 6000, ["clm_dtl_claim_id", "clm_dtl_line_nbr"], {
    "clm_dtl_source_system": (["FACETS", "QNXT", "EPIC", "AMISYS"], [0.45,0.30,0.15,0.10]),
    "clm_dtl_benefit_category": (["Medical", "Surgical", "Prescription Drug", "Preventive Care", "Emergency", "Behavioral Health"], [0.30,0.18,0.22,0.12,0.10,0.08]),
    "clm_dtl_benefit_level": (["In Network", "Out of Network", "Tier 1", "Tier 2", "Non Covered"], [0.58,0.14,0.12,0.10,0.06]),
    "clm_dtl_claim_type": claim_type_vals,
    "clm_dtl_line_status": (["Paid", "Denied", "Pending", "Adjusted", "Reversed"], [0.64,0.18,0.08,0.07,0.03]),
    "clm_dtl_clean_claim_ind": (["Clean", "Requires Review", "Corrected", "Incomplete"], [0.70,0.16,0.10,0.04]),
    "clm_dtl_place_of_service": (["11", "21", "22", "23", "31", "32", "81"], [0.34,0.15,0.22,0.08,0.05,0.04,0.12]),
    "clm_dtl_fee_schedule_code": (["RBR", "ASC", "DRG", "LAB", "DME"], [0.34,0.18,0.16,0.22,0.10]),
    "clm_dtl_rendering_provider_type": (["Primary Care", "Specialist", "Hospital", "Pharmacy", "Lab"], [0.28,0.30,0.18,0.14,0.10]),
    "clm_dtl_rendering_provider_spec": (["Family Medicine", "Cardiology", "Orthopedics", "Radiology", "Behavioral Health"], [0.30,0.18,0.16,0.20,0.16]),
    "clm_dtl_participating_provider": (["Participating", "Non Participating", "Preferred", "Out of Area"], [0.66,0.16,0.12,0.06]),
    "clm_dtl_adjudication_status": (["Auto Adjudicated", "Manual Review", "Denied", "Suspended", "Adjusted"], [0.58,0.20,0.12,0.06,0.04]),
    "clm_dtl_procedure_code": (["99213", "99214", "93000", "80053", "36415", "J0585", "D0120", "99396"], [0.22,0.18,0.12,0.16,0.13,0.05,0.06,0.08]),
    "clm_dtl_procedure_modifier": (["25", "59", "TC", "GP", "RT"], [0.30,0.20,0.18,0.17,0.15]),
    "clm_dtl_revenue_code": (["0450", "0300", "0360", "0510", "0636"], [0.18,0.24,0.16,0.22,0.20]),
    "clm_dtl_cob_rule": (["Primary Pays", "Secondary Coordination", "Medicare Crossover", "No COB"], [0.60,0.18,0.10,0.12]),
    "clm_dtl_wrap_network": (["Core Network", "Wrap Network", "Rental Network", "Out of Network"], [0.58,0.20,0.12,0.10])
}, {})

