
def top_authors_sql():
    min_rating = 5
    min_book_count = 2
    return (
        # sql
        [("""
            CREATE OR REPLACE FUNCTION top_authors()
                RETURNS SETOF test_app_author AS $$
            BEGIN
                RETURN QUERY
                  SELECT au.*
                    FROM test_app_author au
                    WHERE (SELECT COUNT(*) FROM test_app_book ab
                           WHERE ab.author_id = au.id AND ab.rating > %s) > %s;
            END;
            $$ LANGUAGE plpgsql;
          """, [min_rating, min_book_count])],

        # reverse sql
        'DROP FUNCTION top_authors()',
    )
