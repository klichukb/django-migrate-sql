
def top_authors_sql():
    min_rating = 5
    return (
        # sql
        [("""
            CREATE OR REPLACE FUNCTION top_books()
                RETURNS SETOF test_app_book AS $$
            BEGIN
                RETURN QUERY
                    SELECT * FROM test_app_book ab
                    WHERE ab.rating > %s
                    ORDER BY ab.rating DESC;
            END;
            $$ LANGUAGE plpgsql;
          """, [min_rating])],

        # reverse sql
        'DROP FUNCTION top_books()',
    )
