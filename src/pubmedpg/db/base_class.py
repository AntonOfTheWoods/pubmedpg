from typing import Any
import re

from sqlalchemy.ext.declarative import as_declarative, declared_attr

table_pattern = re.compile(r'(?<!^)(?=[A-Z])')


@as_declarative()
class Base:
    id: Any
    __name__: str

    # Generate __tablename__ automatically
    @declared_attr
    def __tablename__(cls) -> str:  # pylint: disable=E0213
        return table_pattern.sub('_', cls.__name__).lower()
