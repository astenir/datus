#!/usr/bin/env python3
"""
Example usage script for the Redshift adapter.

This script demonstrates how to use the Redshift adapter to connect
to a Redshift cluster and perform various operations.

IMPORTANT: Update the configuration section below with your actual
Redshift credentials before running this script.
"""

from datus_redshift import RedshiftConnector, RedshiftConfig


def main():
    """Main function demonstrating Redshift adapter usage."""
    
    # ========================================
    # CONFIGURATION
    # ========================================
    # TODO: Update these values with your actual Redshift credentials
    config = RedshiftConfig(
        host="your-cluster.region.redshift.amazonaws.com",  # e.g., "my-cluster.abc123.us-west-2.redshift.amazonaws.com"
        username="your_username",                            # Your Redshift username
        password="your_password",                            # Your Redshift password
        database="dev",                                      # Database name (default is 'dev')
        schema="public",                                     # Schema name (default is 'public')
        port=5439,                                          # Port (default is 5439)
        ssl=True,                                           # Use SSL (recommended)
        timeout_seconds=30                                  # Connection timeout
    )
    
    # ========================================
    # EXAMPLE: Using IAM Authentication
    # ========================================
    # Uncomment below to use IAM authentication instead:
    """
    config = RedshiftConfig(
        host="your-cluster.region.redshift.amazonaws.com",
        username="your_iam_username",
        database="dev",
        iam=True,
        cluster_identifier="your-cluster",
        region="us-west-2",
        access_key_id="YOUR_ACCESS_KEY_ID",
        secret_access_key="YOUR_SECRET_ACCESS_KEY"
    )
    """
    
    # Create connector instance
    print("=" * 60)
    print("Redshift Adapter - Example Usage")
    print("=" * 60)
    
    try:
        # ========================================
        # 1. CREATE CONNECTION
        # ========================================
        print("\n1. Creating connection to Redshift...")
        connector = RedshiftConnector(config)
        print("   ✓ Connector created successfully")
        
        # ========================================
        # 2. TEST CONNECTION
        # ========================================
        print("\n2. Testing connection...")
        result = connector.test_connection()
        if result["success"]:
            print(f"   ✓ {result['message']}")
            print(f"   Connected to database: {result.get('database', 'N/A')}")
        else:
            print(f"   ✗ Connection failed")
            return
        
        # ========================================
        # 3. GET DATABASES
        # ========================================
        print("\n3. Listing databases...")
        databases = connector.get_databases(include_sys=False)
        print(f"   Found {len(databases)} database(s):")
        for db in databases[:5]:  # Show first 5
            print(f"     - {db}")
        if len(databases) > 5:
            print(f"     ... and {len(databases) - 5} more")
        
        # ========================================
        # 4. GET SCHEMAS
        # ========================================
        print("\n4. Listing schemas...")
        schemas = connector.get_schemas(include_sys=False)
        print(f"   Found {len(schemas)} schema(s):")
        for schema in schemas[:10]:  # Show first 10
            print(f"     - {schema}")
        if len(schemas) > 10:
            print(f"     ... and {len(schemas) - 10} more")
        
        # ========================================
        # 5. GET TABLES
        # ========================================
        print("\n5. Listing tables in 'public' schema...")
        tables = connector.get_tables(schema_name="public")
        if tables:
            print(f"   Found {len(tables)} table(s):")
            for table in tables[:10]:  # Show first 10
                print(f"     - {table}")
            if len(tables) > 10:
                print(f"     ... and {len(tables) - 10} more")
        else:
            print("   No tables found in 'public' schema")
        
        # ========================================
        # 6. EXECUTE SIMPLE QUERY
        # ========================================
        print("\n6. Executing simple query...")
        sql = "SELECT current_database() as database, current_schema() as schema, current_user as user"
        result = connector.execute_query(sql, result_format="list")
        
        if result.success:
            print(f"   ✓ Query executed successfully")
            print(f"   Rows returned: {result.row_count}")
            if result.sql_return:
                print(f"   Result: {result.sql_return[0]}")
        else:
            print(f"   ✗ Query failed: {result.error}")
        
        # ========================================
        # 7. EXECUTE QUERY WITH DIFFERENT FORMATS
        # ========================================
        print("\n7. Testing different result formats...")
        test_sql = "SELECT 1 as id, 'test' as name, 99.99 as value UNION ALL SELECT 2, 'example', 123.45"
        
        # CSV format
        result_csv = connector.execute_query(test_sql, result_format="csv")
        if result_csv.success:
            print(f"   ✓ CSV format: {len(result_csv.sql_return)} characters")
        
        # Pandas format
        result_pandas = connector.execute_query(test_sql, result_format="pandas")
        if result_pandas.success:
            print(f"   ✓ Pandas format: DataFrame with {len(result_pandas.sql_return)} rows")
        
        # Arrow format
        result_arrow = connector.execute_query(test_sql, result_format="arrow")
        if result_arrow.success:
            print(f"   ✓ Arrow format: Table with {result_arrow.sql_return.num_rows} rows")
        
        # List format
        result_list = connector.execute_query(test_sql, result_format="list")
        if result_list.success:
            print(f"   ✓ List format: {len(result_list.sql_return)} rows")
        
        # ========================================
        # 8. GET TABLE SCHEMA (if tables exist)
        # ========================================
        if tables and len(tables) > 0:
            print(f"\n8. Getting schema for table '{tables[0]}'...")
            schema_info = connector.get_schema(
                schema_name="public",
                table_name=tables[0]
            )
            if schema_info:
                print(f"   ✓ Found {len(schema_info) - 1} column(s):")  # -1 for the summary dict
                for col in schema_info[:-1]:  # Skip the summary dict
                    print(f"     - {col['name']}: {col['type']} (nullable: {col['nullable']})")
        else:
            print("\n8. Skipping table schema retrieval (no tables found)")
        
        # ========================================
        # 9. GET VIEWS
        # ========================================
        print("\n9. Listing views...")
        views = connector.get_views(schema_name="public")
        if views:
            print(f"   Found {len(views)} view(s):")
            for view in views[:5]:
                print(f"     - {view}")
        else:
            print("   No views found in 'public' schema")
        
        # ========================================
        # 10. GET MATERIALIZED VIEWS
        # ========================================
        print("\n10. Listing materialized views...")
        mvs = connector.get_materialized_views(schema_name="public")
        if mvs:
            print(f"    Found {len(mvs)} materialized view(s):")
            for mv in mvs[:5]:
                print(f"      - {mv}")
        else:
            print("    No materialized views found in 'public' schema")
        
        # ========================================
        # SUCCESS MESSAGE
        # ========================================
        print("\n" + "=" * 60)
        print("✓ All operations completed successfully!")
        print("=" * 60)
        print("\nThe Redshift adapter is working correctly!")
        print("You can now use it with Datus Agent.")
        
    except Exception as e:
        # ========================================
        # ERROR HANDLING
        # ========================================
        print("\n" + "=" * 60)
        print("✗ Error occurred:")
        print("=" * 60)
        print(f"{type(e).__name__}: {str(e)}")
        print("\nPlease check:")
        print("  1. Your Redshift cluster is running and accessible")
        print("  2. Your credentials are correct")
        print("  3. Your security group allows connections from your IP")
        print("  4. You have network connectivity to AWS")
        return 1
        
    finally:
        # ========================================
        # CLEANUP
        # ========================================
        print("\nClosing connection...")
        connector.close()
        print("✓ Connection closed")
    
    return 0


if __name__ == "__main__":
    """
    Run this script to test the Redshift adapter.
    
    Before running:
    1. Install the adapter: pip install -e .
    2. Update the configuration section above with your credentials
    3. Run: python example_usage.py
    """
    exit(main())

