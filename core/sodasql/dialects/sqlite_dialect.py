#  Copyright 2020 Soda
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#   http://www.apache.org/licenses/LICENSE-2.0
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
from datetime import date

import logging
from typing import Union, Optional
import sqlite3

from sodasql.scan.dialect import Dialect, SQLITE, KEY_WAREHOUSE_TYPE
from sodasql.scan.parser import Parser

"""

"""

logger = logging.getLogger(__name__)


class SQLiteDialect(Dialect):

    def __init__(self, parser: Parser = None, type: str = SQLITE):
        super().__init__(type)
        if parser:
            self.dbfile = parser.get_str_required_env('dbfile')

    def default_connection_properties(self, params: dict):
        return {
            KEY_WAREHOUSE_TYPE: SQLITE,
            'dbfile': 'example.db'
        }

    def default_env_vars(self, params: dict):
        return {
            'SQLITE_DBFILE': params.get('dbfile', 'example.db'),
        }

    def sql_tables_metadata_query(self, limit: Optional[int] = None, filter: str = None):
        sql = (f"SELECT TABLE_NAME \n"
               f"FROM information_schema.tables \n"
               f"WHERE lower(table_schema)='{self.schema.lower()}'")
        if limit is not None:
            sql += f"\n LIMIT {limit}"
        return sql

    def sql_connection_test(self):
        pass

    def create_connection(self):
        try:
            conn = sqlite3.connect(self.dbfile)
            return conn
        except Exception as e:
            self.try_to_raise_soda_sql_exception(e)

    def query_table(self, table_name):
        query = f"""
        SELECT *
        FROM {table_name}
        LIMIT 1
        """
        return query

    def sql_test_connection(self) -> Union[Exception, bool]:
        return True

    def sql_columns_metadata_query(self, table_name: str) -> str:
        sql = (f"SELECT name, type, \n"
               f"case [notnull] \n"
               f"  WHEN 0 then 'YES' \n"
               f"  ELSE 'NO' \n"
               f"END as is_nullable \n"
               f"FROM pragma_table_info('{table_name}') \n")

        return sql

    def is_text(self, column_type: str):
        # "Note that numeric arguments in parentheses that following
        # the type name (ex: "VARCHAR(255)") are ignored by SQLite" - https://www.sqlite.org/datatype3.html
        # So VARCHAR(255) is same as VARCHAR(2), that's why we only check for startswith here
        return column_type.upper().startswith(('CHARACTER', 'VARCHAR', 'VARYING CHARACTER', 'NCHAR',
                                               'NATIVE CHARACTER', 'NVARCHAR', 'TEXT', 'CLOB'))

    def is_number(self, column_type: str):
        return column_type.upper() in ['INT', 'INTEGER', 'TINYINT', 'SMALLINT', 'MEDIUMINT', 'BIGINT',
                                       'UNSIGNED BIG INT',
                                       'INT2', 'INT8']

    def is_time(self, column_type: str):
        return column_type.upper() in ['DATE', 'DATETIMEOFFSET', 'DATETIME2', 'SMALLDATETIME', 'DATETIME', 'TIME']

    def qualify_table_name(self, table_name: str) -> str:
        return f'"{table_name}"'

    def sql_expr_regexp_like(self, expr: str, pattern: str):
        return f"{expr} LIKE '{self.qualify_regex(pattern)}'"

    def sql_expr_length(self, expr):
        return f'LENGTH({expr})'

    def sql_expr_variance(self, expr: str):
        logger.warning("variance is not supported ")
        # SUM((var-(SELECT AVG(var) FROM TableX))*
        #            (var-(SELECT AVG(var) FROM TableX)) ) / (COUNT(var)-1)
        return f'AVG({expr}*{expr}) - AVG({expr})*AVG({expr})'

    def sql_expr_stddev(self, expr: str):
        return f'(AVG({expr}*{expr}) - AVG({expr})*AVG({expr}))'

    def sql_expr_limit(self, count):
        return f'OFFSET 0 ROWS FETCH NEXT {count} ROWS ONLY'

    def sql_select_with_limit(self, table_name, count):
        return f'SELECT TOP {count} * FROM {table_name}'

    def sql_expr_cast_text_to_number(self, quoted_column_name, validity_format):
        if validity_format == 'number_whole':
            return f"CAST({quoted_column_name} AS {self.data_type_decimal})"
        not_number_pattern = self.qualify_regex(r"[^-\d\.\,]")
        comma_pattern = self.qualify_regex(r"\,")
        return f"CAST(REGEXP_REPLACE(REGEXP_REPLACE({quoted_column_name}, '{not_number_pattern}', '', 'g'), " \
               f"'{comma_pattern}', '.', 'g') AS {self.data_type_decimal})"
