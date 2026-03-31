import csv
import random

tables = ["employees", "departments", "orders", "invoices", "accounts", "customers", "products", "inventory", "transactions", "payrolls", "log_entries", "audit_trail"]
columns = ["status", "salary", "amount", "created_date", "total_value", "region", "category", "price", "is_active", "rating", "department_id", "email"]
statuses = ["ACTIVE", "PENDING", "CLOSED", "DRAFT", "ARCHIVED", "DELETED", "NEW", "FAILED"]
bip_groups = ["G_EMP", "G_ORDER", "G_INVOICE", "G_DEPT", "G_CUSTOMER", "G_SUMMARY", "G_DETAILS"]
bip_elements = ["NAME", "TOTAL", "AMOUNT", "ID", "STATUS", "DATE", "CURRENCY", "REFERENCE"]
oci_resources = ["oci_core_vcn", "oci_core_subnet", "oci_core_instance", "oci_identity_policy", "oci_objectstorage_bucket", "oci_database_autonomous_database", "oci_functions_function"]

templates = {
    "SQL": [
        ("Analyze this SQL: SELECT * FROM {table} WHERE {col} = '{status}' ;", 
         "The agent should explain the SELECT query on {table}, identify the '{status}' filter, and suggest explicitly naming columns instead of 'SELECT *' for better maintainability."),
        ("Review this SQL join: SELECT a.id, b.name FROM {table}_a a, {table}_b b WHERE a.b_id = b.id;", 
         "The agent should flag the implicit ANSI 89 join syntax on {table}_a and recommend rewriting it using the modern ANSI 92 INNER JOIN syntax for improved readability."),
        ("Optimize this query: SELECT count(1) FROM {table} WHERE {col} IS NOT NULL;",
         "The agent should advise ensuring an index exists on {col} in {table} to prevent a full table scan when counting records."),
        ("Check this SQL: DELETE FROM {table} WHERE {col} < 1000 AND status = '{status}';",
         "The agent should warn about bulk deletions on {table} potentially locking rows or blowing up undo segments. Suggests batching via PL/SQL if the data volume is massive."),
         ("Evaluate: SELECT {col}, SUM(amount) FROM {table} GROUP BY {col} ORDER BY 2 DESC;",
         "The agent should identify this as an aggregation on {table} and confirm that {col} is properly indexed for efficient grouping and sorting operations."),
         ("Review index usage: SELECT /*+ INDEX({table} idx_{col}) */ * FROM {table} WHERE {col} = 5;",
         "The agent should note the use of an optimizer hint on {table} and recommend verifying if the cost-based optimizer (CBO) would naturally pick a better execution path without hardcoded hints.")
    ],
    "PLSQL": [
        ("Evaluate this PL/SQL loop: FOR rec IN (SELECT id FROM {table}) LOOP UPDATE {table} SET {col} = 100 WHERE id = rec.id; END LOOP;", 
         "The agent should detect 'Row-by-Row processing' on {table}. Strongly recommend refactoring into a single bulk UPDATE statement or using FORALL for massive performance gains."),
        ("Analyze this exception handling in pkg_{table}: EXCEPTION WHEN OTHERS THEN NULL;", 
         "The agent should flag 'WHEN OTHERS THEN NULL' as a critical anti-pattern (silently swallowing exceptions) and recommend proper logging and re-raising the error."),
        ("Review this function: FUNCTION get_{col} RETURN NUMBER IS v NUMBER; BEGIN SELECT {col} INTO v FROM {table} WHERE ROWNUM=1; RETURN v; END;",
         "The agent should warn about fetching without an ORDER BY in {table}, making the result non-deterministic, and missing necessary NO_DATA_FOUND exception handling."),
        ("Evaluate PL/SQL block: DECLARE v_count NUMBER; BEGIN SELECT count(*) INTO v_count FROM {table}; IF v_count > 0 THEN UPDATE {table} SET status='{status}'; END IF; END;",
         "The agent should flag this as an unnecessary double-read logic. It should suggest just running the UPDATE directly on {table} and relying on the implicit SQL%ROWCOUNT variable.")
    ],
    "GROOVY": [
        ("Review this Groovy script for EPM: def records = app.getDimension('{table}').getMembers(Input);", 
         "The agent should explain that retrieving all members of '{table}' into memory risks server memory exhaustion. Proposing iterative or batched approaches is recommended."),
        ("Analyze this Groovy REST call: def url = new URL('http://api.internal/data/{table}'); println url.text;", 
         "The agent should identify the HTTP GET request. It should warn about the lack of timeout configurations, missing try-catch error handling, and security risks of using unencrypted HTTP."),
        ("Check this JSON parsing snippet: def json = new JsonSlurper().parseText(responseBody); println json.{col};",
         "The agent should confirm the correct use of JsonSlurper. It should strongly advise handling malformed JSON exceptions and adding null checks on '{col}' before printing/accessing."),
        ("Review Jenkins Groovy pipeline snippet: sh 'sqlplus user/pass@db @script.sql --table={table}'",
         "The agent should immediately flag hardcoded database credentials in the shell execution step. It must recommend using Jenkins Credentials Binding or Vault integration instead.")
    ],
    "BIP": [
        ("Review this BIP Data Model Query for {table} report: SELECT t.{col}, SUM(amount) FROM {table} t WHERE t.status = :P_STATUS GROUP BY t.{col};", 
         "The agent should validate the BI Publisher SQL, noting the bind parameter ':P_STATUS'. It should advise verifying index coverage on '{col}' and the status column on {table}."),
        ("Validate this BIP RTF Template structure: <?for-each:{group}?> <value><?{element}?></value> <?end for-each?>", 
         "The agent should confirm the correct BIP 'for-each' looping syntax over the XML data group '{group}', outputting the placeholder '{element}' accurately."),
        ("Check BIP multi-select parameter query: SELECT * FROM {table} WHERE {col} IN (:P_{col})",
         "The agent should validate the IN clause for a BI Publisher multi-select menu, confirming that the data model must have this parameter configured appropriately to allow multiple values."),
        ("Review BIP burst definition SQL: SELECT {col} AS ""KEY"", '{status}' AS ""TEMPLATE"", 'en-US' AS ""LOCALE"" FROM {table}",
         "The agent should identify a BI Publisher bursting control query driving report distribution routing based on {table}. Suggests verifying that the selected 'KEY' ensures proper delivery grouping.")
    ],
    "OCI": [
        ("Review this OCI Terraform snippet: resource \"{resource}\" \"app_{resource}\" {{ display_name = \"{table}_app\" }}", 
         "The agent should identify the configuration for Oracle Cloud Infrastructure resource '{resource}'. It should suggest adding required attributes like 'compartment_id' and checking any dependent networking modules if applicable."),
        ("Analyze this OCI CLI command: oci compute instance launch --shape VM.Standard.E4.Flex --subnet-id {col}",
         "The agent should identify an OCI compute instance launch request. It should warn about executing CLI locally without checking identity policies (IAM), and suggest tracking this in Infrastructure-as-Code setups instead (e.g. Terraform)."),
        ("Evaluate OCI policy: Allow group {table}_Admins to manage {resource} in tenancy",
         "The agent should flag this IAM policy as extremely permissive. It should strongly recommend restricting 'manage' rights for '{resource}' to a specific compartment rather than the entire enterprise tenancy level.")
    ]
}

def generate_row(id_val):
    category = random.choice(list(templates.keys()))
    template, expected_template = random.choice(templates[category])
    
    t = random.choice(tables)
    c = random.choice(columns)
    s = random.choice(statuses)
    g = random.choice(bip_groups)
    e = random.choice(bip_elements)
    r = random.choice(oci_resources)
    
    query = template.format(table=t, col=c, status=s, group=g, element=e, resource=r)
    expected = expected_template.format(table=t, col=c, status=s, group=g, element=e, resource=r)
    
    return [id_val, query, expected]

if __name__ == "__main__":
    filepath = r'c:\Users\msshe\Documents\Projects\ReverseCodeEngineeringAgent\test_queries.csv'
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["id", "query", "expected"])
        for i in range(1, 501):
            writer.writerow(generate_row(i))
    print("CSV updated with 500 records.")
